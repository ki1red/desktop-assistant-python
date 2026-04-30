import threading
import time

from pynput import keyboard

from app.session.state import session_state
from app.adaptive.history import register_negative_feedback, register_positive_feedback
from app.events.notifier import AssistantNotifier
from app.runtime_control import runtime_control
from app.logger import get_logger
from app.settings_service import settings_service
from app.speech.recorder import MicrophoneSelectionError
from app.speech.vosk_wake_detector import VoskWakeDetector, VoskWakeDetectorError


logger = get_logger("background_service")


class BackgroundAssistantService:
    def __init__(self):
        self.pipeline = None
        self._pipeline_lock = threading.RLock()
        self._pipeline_warmup_thread = None

        self.notifier = AssistantNotifier()
        self.listener = None
        self._running = False
        self.is_paused = False
        self._worker_thread = None

        self.hotkey = "<ctrl>+<alt>+<space>"
        self.cancel_on_second_press = True

        self.activation_mode = "hotkey"
        self.voice_activation_phrase = "ассистент"
        self.wake_check_interval_sec = 0.35
        self.wake_post_activation_cooldown_sec = 2.5

        self._wake_thread = None
        self._wake_stop_event = None
        self._wake_lock = threading.RLock()
        self._wake_suppressed_until = 0.0
        self._wake_detector = VoskWakeDetector()

        self._apply_config(settings_service.get_all())
        settings_service.subscribe(self._on_settings_changed)

    def _get_pipeline(self):
        with self._pipeline_lock:
            if self.pipeline is None:
                logger.info("Создание AssistantPipeline по требованию.")

                from app.assistant_pipeline import AssistantPipeline

                self.pipeline = AssistantPipeline()
                logger.info("AssistantPipeline создан.")

            return self.pipeline

    def _warmup_pipeline_worker(self):
        try:
            logger.info("Прогрев AssistantPipeline запущен.")
            self._get_pipeline()
            logger.info("Прогрев AssistantPipeline завершён.")
        except Exception as e:
            logger.exception("Ошибка прогрева AssistantPipeline: %s", e)

    def _ensure_pipeline_warmup_started(self):
        with self._pipeline_lock:
            if self.pipeline is not None:
                return

            if self._pipeline_warmup_thread is not None and self._pipeline_warmup_thread.is_alive():
                return

            self._pipeline_warmup_thread = threading.Thread(
                target=self._warmup_pipeline_worker,
                daemon=True,
            )
            self._pipeline_warmup_thread.start()

    def _apply_config(self, config_snapshot: dict):
        bg = config_snapshot.get("background", {})
        assistant = config_snapshot.get("assistant", {})

        new_hotkey = bg.get("hotkey", "<ctrl>+<alt>+<space>")
        new_cancel = bg.get("double_press_cancels", True)

        new_activation_mode = assistant.get("activation_mode", "hotkey")
        new_voice_phrase = assistant.get("voice_activation_phrase", "ассистент")
        new_wake_check_interval_sec = float(assistant.get("wake_check_interval_sec", 0.35))
        new_wake_cooldown = float(assistant.get("wake_post_activation_cooldown_sec", 2.5))

        hotkey_changed = new_hotkey != self.hotkey
        cancel_changed = new_cancel != self.cancel_on_second_press
        activation_changed = new_activation_mode != self.activation_mode

        self.hotkey = new_hotkey
        self.cancel_on_second_press = new_cancel

        self.activation_mode = new_activation_mode
        self.voice_activation_phrase = (new_voice_phrase or "ассистент").strip()
        self.wake_check_interval_sec = max(0.10, min(new_wake_check_interval_sec, 3.0))
        self.wake_post_activation_cooldown_sec = max(0.5, min(new_wake_cooldown, 10.0))

        self._wake_detector.reload_from_settings(config_snapshot)

        if self.activation_mode == "voice":
            self._ensure_pipeline_warmup_started()

        if self._running and (hotkey_changed or cancel_changed):
            logger.info(
                "Настройки hotkey обновлены на лету: hotkey=%s cancel=%s",
                self.hotkey,
                self.cancel_on_second_press,
            )
            self._restart_listener()

        if self._running and activation_changed:
            logger.info("Режим активации изменён: %s", self.activation_mode)
            self._sync_wake_listener()

    def _on_settings_changed(self, config_snapshot: dict):
        self._apply_config(config_snapshot)

    def _is_microphone_allowed(self) -> bool:
        cfg = settings_service.get_all()
        audio = cfg.get("audio", {})
        return bool(audio.get("microphone_enabled", True))

    def _beep(self):
        try:
            import winsound
            winsound.Beep(1200, 120)
        except Exception:
            pass

    def _suppress_wake_for(self, seconds: float):
        until = time.time() + max(0.0, float(seconds))
        self._wake_suppressed_until = max(self._wake_suppressed_until, until)

    def _is_wake_suppressed(self) -> bool:
        return time.time() < self._wake_suppressed_until

    def _cleanup_dead_thread(self):
        if self._worker_thread is not None and not self._worker_thread.is_alive():
            self._worker_thread = None

    def is_busy(self) -> bool:
        self._cleanup_dead_thread()
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _prepare_for_new_activation(self):
        """
        Готовит ассистента к новой записи:
        - останавливает TTS;
        - временно подавляет wake-listener.
        """
        try:
            self.notifier.stop_speaking()
        except Exception as e:
            logger.debug("Не удалось остановить озвучку перед активацией: %s", e)

        self._suppress_wake_for(1.0)

    def _request_activation(self, source: str = "hotkey", initial_text: str | None = None) -> bool:
        """
        Запускает обработку команды.

        Для voice-mode после Vosk-срабатывания:
        - сначала гарантируем готовность pipeline;
        - только потом подаём beep;
        - только потом начинаем реальную запись команды.
        """
        if self.is_paused:
            logger.info("Активация проигнорирована: ассистент на паузе. source=%s", source)
            return False

        self._prepare_for_new_activation()

        if self.is_busy():
            if source == "hotkey" and self.cancel_on_second_press:
                logger.info("Запрошена отмена текущей операции.")
                print("[BG] Запрошена отмена текущей операции.")

                runtime_control.cancel_job()

                if self.pipeline is not None:
                    self.pipeline.cancel_current_operation()

                self._suppress_wake_for(self.wake_post_activation_cooldown_sec)
                self.notifier.say("Текущая операция отменена.")
            else:
                logger.info("Ассистент уже обрабатывает предыдущую команду. source=%s", source)

                if source == "hotkey":
                    print("[BG] Ассистент уже обрабатывает предыдущую команду.")
                    self.notifier.say("Я ещё работаю.")

            return False

        def worker():
            runtime_control.start_job()

            try:
                self._prepare_for_new_activation()

                # ВАЖНО:
                # сначала гарантируем готовность pipeline/Whisper,
                # и только потом сигнализируем пользователю, что можно говорить.
                pipeline = self._get_pipeline()

                if source == "voice":
                    logger.info("Голосовая активация Vosk сработала.")
                    print("[BG] Голосовая активация Vosk сработала.")
                else:
                    logger.info("Горячая клавиша нажата. Слушаю команду...")
                    print("[BG] Горячая клавиша нажата. Слушаю команду...")

                self._suppress_wake_for(1.5)
                self._beep()

                if initial_text:
                    pipeline.run_text(
                        text=initial_text,
                        language="ru",
                        source="wake_initial_text",
                        announce_processing=True,
                    )
                else:
                    pipeline.run_once()

            except Exception as e:
                logger.exception("Ошибка во время выполнения команды: %s", e)
                print(f"[BG][ERROR] Ошибка во время выполнения команды: {e}")
                self.notifier.say("Произошла ошибка во время выполнения команды.")

            finally:
                self._suppress_wake_for(self.wake_post_activation_cooldown_sec)
                runtime_control.finish_job()

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

        return True

    def _on_activate(self):
        self._request_activation(source="hotkey")

    def _can_listen_for_wake(self) -> bool:
        return (
            self.activation_mode == "voice"
            and not self._is_wake_suppressed()
            and not self.notifier.is_speaking()
            and not self.is_paused
            and not self.is_busy()
            and self._is_microphone_allowed()
        )

    def _wait_until_command_finishes(self, stop_event: threading.Event):
        """
        После успешного wake-срабатывания не даём Vosk снова слушать,
        пока текущая команда ещё записывается/распознаётся/выполняется.
        """
        while not stop_event.is_set():
            if not self.is_busy() and not self._is_wake_suppressed():
                return
            stop_event.wait(0.10)

    def _wake_worker(self, stop_event: threading.Event):
        logger.info(
            "Wake-listener (Vosk) запущен. phrase=%r sample_rate=%s block_size=%s model=%r",
            self._wake_detector.phrase,
            self._wake_detector.sample_rate,
            self._wake_detector.block_size,
            self._wake_detector.model_path_setting,
        )

        last_error_log_time = 0.0

        while not stop_event.is_set():
            try:
                if self.activation_mode != "voice":
                    break

                if not self._can_listen_for_wake():
                    stop_event.wait(self.wake_check_interval_sec)
                    continue

                detected = self._wake_detector.wait_for_wake(
                    stop_event=stop_event,
                    can_listen=self._can_listen_for_wake,
                )

                if detected:
                    logger.info("Vosk распознал wake-фразу: %r", self._wake_detector.phrase)
                    print(f"[BG] Vosk распознал wake-фразу: {self._wake_detector.phrase}")

                    activated = self._request_activation(source="voice")
                    if activated:
                        self._wait_until_command_finishes(stop_event)

                    continue

                stop_event.wait(self.wake_check_interval_sec)

            except MicrophoneSelectionError as e:
                now = time.time()

                if now - last_error_log_time > 10:
                    logger.warning("Wake-listener Vosk: проблема микрофона: %s", e)
                    last_error_log_time = now

                stop_event.wait(1.0)

            except VoskWakeDetectorError as e:
                now = time.time()

                if now - last_error_log_time > 10:
                    logger.error("Wake-listener Vosk недоступен: %s", e)
                    last_error_log_time = now

                stop_event.wait(2.0)

            except Exception as e:
                now = time.time()

                if now - last_error_log_time > 10:
                    logger.exception("Wake-listener Vosk: ошибка: %s", e)
                    last_error_log_time = now

                stop_event.wait(1.0)

        logger.info("Wake-listener (Vosk) остановлен.")

    def _start_wake_listener(self):
        with self._wake_lock:
            if self._wake_thread is not None and self._wake_thread.is_alive():
                return

            stop_event = threading.Event()
            self._wake_stop_event = stop_event

            self._wake_thread = threading.Thread(
                target=self._wake_worker,
                args=(stop_event,),
                daemon=True,
            )
            self._wake_thread.start()

    def _stop_wake_listener(self):
        with self._wake_lock:
            stop_event = self._wake_stop_event
            thread = self._wake_thread

            if stop_event is not None:
                stop_event.set()

            if thread is not None and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=2.0)

            if thread is None or not thread.is_alive():
                self._wake_thread = None
                self._wake_stop_event = None

    def _sync_wake_listener(self):
        if not self._running:
            return

        if self.activation_mode == "voice":
            self._ensure_pipeline_warmup_started()
            self._start_wake_listener()
        else:
            self._stop_wake_listener()

    def _on_like(self):
        last = session_state.last_resolved

        if last and last.target_path:
            register_positive_feedback(last.target_path)
            logger.info("Лайк сохранён: %s", last.target_name)
            print(f"[BG] Лайк сохранён: {last.target_name}")
            self.notifier.say_random("like")
        else:
            logger.info("Нет последней команды для лайка.")
            print("[BG] Нет последней команды для лайка.")
            self.notifier.say("Нет последней команды для лайка.")

    def _on_dislike(self):
        last = session_state.last_resolved

        if last and last.target_path:
            register_negative_feedback(last.target_path)
            logger.info("Дизлайк сохранён: %s", last.target_name)
            print(f"[BG] Дизлайк сохранён: {last.target_name}")
            self.notifier.say_random("dislike")
        else:
            logger.info("Нет последней команды для дизлайка.")
            print("[BG] Нет последней команды для дизлайка.")
            self.notifier.say("Нет последней команды для дизлайка.")

    def pause(self):
        self.is_paused = True
        logger.info("Ассистент поставлен на паузу.")

    def resume(self):
        self.is_paused = False
        logger.info("Ассистент возобновлён.")

    def _create_listener(self):
        open_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(self.hotkey),
            self._on_activate,
        )
        like_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<alt>+<up>"),
            self._on_like,
        )
        dislike_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<alt>+<down>"),
            self._on_dislike,
        )

        def on_press(key):
            canonical = self.listener.canonical(key)
            open_hotkey.press(canonical)
            like_hotkey.press(canonical)
            dislike_hotkey.press(canonical)

        def on_release(key):
            canonical = self.listener.canonical(key)
            open_hotkey.release(canonical)
            like_hotkey.release(canonical)
            dislike_hotkey.release(canonical)

        return keyboard.Listener(on_press=on_press, on_release=on_release)

    def _restart_listener(self):
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass

            self.listener = None

        try:
            self.listener = self._create_listener()
            self.listener.start()
            logger.info("Listener перезапущен с новой горячей клавишей: %s", self.hotkey)

        except ValueError as e:
            logger.exception("Ошибка формата hotkey: %s", e)
            print(f"[BG][ERROR] Ошибка формата hotkey: {e}")
            self.notifier.say("Неверный формат горячей клавиши.")

        except Exception as e:
            logger.exception("Не удалось запустить listener горячих клавиш: %s", e)
            print(f"[BG][ERROR] Не удалось запустить listener горячих клавиш: {e}")
            self.notifier.say("Не удалось запустить горячую клавишу.")

    def start(self):
        if self._running:
            return

        self._running = True

        if self.activation_mode == "voice":
            self._ensure_pipeline_warmup_started()

        self._restart_listener()
        self._sync_wake_listener()

        logger.info(
            "Фоновый сервис запущен. Hotkey: %s activation_mode=%s wake_phrase=%r wake_engine=vosk",
            self.hotkey,
            self.activation_mode,
            self.voice_activation_phrase,
        )

        print(f"[BG] Фоновый режим запущен. Горячая клавиша: {self.hotkey}")
        print(f"[BG] Режим активации: {self.activation_mode}")
        print("[BG] Wake engine: Vosk")
        print("[BG] Лайк: Ctrl+Alt+Up | Дизлайк: Ctrl+Alt+Down")
        print("[BG] Повторное нажатие hotkey во время работы мгновенно отменяет текущую операцию.")

    def stop(self):
        self._stop_wake_listener()

        try:
            self.notifier.stop_speaking()
        except Exception:
            pass

        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass

            self.listener = None

        if self.is_busy() and self.pipeline is not None:
            self.pipeline.cancel_current_operation()
        elif self.is_busy():
            runtime_control.cancel_job()

        self._running = False
        logger.info("Фоновый сервис остановлен.")