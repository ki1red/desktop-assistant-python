import re
import threading
import time

from pynput import keyboard

from app.session.state import session_state
from app.adaptive.history import register_negative_feedback, register_positive_feedback
from app.events.notifier import AssistantNotifier
from app.runtime_control import runtime_control
from app.logger import get_logger
from app.settings_service import settings_service
from app.speech.recorder import (
    record_wake_audio_to_wav,
    delete_temp_file,
    MicrophoneSelectionError,
    NoMicrophoneSignalError,
)
from app.speech.transcriber import NoSpeechDetected


logger = get_logger("background_service")


def _normalize_wake_text(text: str) -> str:
    text = (text or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class BackgroundAssistantService:
    def __init__(self):
        self.pipeline = None

        self.notifier = AssistantNotifier()
        self.listener = None
        self._running = False
        self.is_paused = False
        self._worker_thread = None

        self.hotkey = "<ctrl>+<alt>+<space>"
        self.cancel_on_second_press = True

        self.activation_mode = "hotkey"
        self.voice_activation_phrase = "ассистент"
        self.wake_record_seconds = 1.8
        self.wake_check_interval_sec = 0.35

        self._wake_thread = None
        self._wake_stop_event = None
        self._wake_lock = threading.RLock()

        self._apply_config(settings_service.get_all())
        settings_service.subscribe(self._on_settings_changed)

    def _get_pipeline(self):
        if self.pipeline is None:
            logger.info("Создание AssistantPipeline по требованию.")

            from app.assistant_pipeline import AssistantPipeline

            self.pipeline = AssistantPipeline()
            logger.info("AssistantPipeline создан.")

        return self.pipeline

    def _apply_config(self, config_snapshot: dict):
        bg = config_snapshot.get("background", {})
        assistant = config_snapshot.get("assistant", {})

        new_hotkey = bg.get("hotkey", "<ctrl>+<alt>+<space>")
        new_cancel = bg.get("double_press_cancels", True)

        new_activation_mode = assistant.get("activation_mode", "hotkey")
        new_voice_phrase = assistant.get("voice_activation_phrase", "ассистент")
        new_wake_record_seconds = float(assistant.get("wake_record_seconds", 1.8))
        new_wake_check_interval_sec = float(assistant.get("wake_check_interval_sec", 0.35))

        hotkey_changed = new_hotkey != self.hotkey
        cancel_changed = new_cancel != self.cancel_on_second_press
        activation_changed = new_activation_mode != self.activation_mode

        self.hotkey = new_hotkey
        self.cancel_on_second_press = new_cancel

        self.activation_mode = new_activation_mode
        self.voice_activation_phrase = (new_voice_phrase or "ассистент").strip()
        self.wake_record_seconds = max(0.8, min(new_wake_record_seconds, 4.0))
        self.wake_check_interval_sec = max(0.15, min(new_wake_check_interval_sec, 3.0))

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

    def _cleanup_dead_thread(self):
        if self._worker_thread is not None and not self._worker_thread.is_alive():
            self._worker_thread = None

    def is_busy(self) -> bool:
        self._cleanup_dead_thread()
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _normalize_ai_intent_hint(self, value: str | None) -> str | None:
        if not value:
            return None

        v = str(value).strip().lower()

        allowed = {
            "enable_chat_mode",
            "disable_chat_mode",
            "enable_dictation",
            "disable_dictation",
            "open_file",
            "open_folder",
            "generic_open",
            "search_web",
            "search_youtube",
            "play_music_query",
            "select_candidate",
            "unknown",
        }

        return v if v in allowed else None

    def _run_recognized_text_directly(self, pipeline, recognized_text: str):
        """
        Выполняет уже распознанный текст без повторной записи аудио.

        Нужно для сценария:
        "ассистент открой стим"

        Иначе ассистент услышит wake-фразу, потом начнёт новую запись,
        а команда уже может быть произнесена и потеряна.
        """
        from app.dictation.state import dictation_state
        from app.chat.state import chat_state
        from app.nlu.text_cleanup import cleanup_command_text
        from app.nlu.resources_loader import nlu_resources

        text = (recognized_text or "").strip()
        if not text:
            return None

        print(f"[STT_WAKE_COMMAND] {text}")
        logger.info("Wake-команда после обращения: %s", text)

        if dictation_state.is_enabled():
            return pipeline._handle_dictation(text)

        if chat_state.is_enabled():
            return pipeline._handle_chat_mode(text)

        cleaned_text = cleanup_command_text(text)
        logger.info("Wake-команда после базовой очистки: %s", cleaned_text)

        final_text = cleaned_text
        ai_intent_hint = None
        target_hint = None
        entity_type_hint = None

        ai_cfg = settings_service.get_section("ai", {})
        logger.info(
            "AI flags для wake-команды: enabled=%s apply_to_all_commands=%s provider=%s",
            ai_cfg.get("enabled", False),
            ai_cfg.get("apply_to_all_commands", False),
            ai_cfg.get("provider", "unknown"),
        )

        if ai_cfg.get("enabled", False) and ai_cfg.get("apply_to_all_commands", False):
            logger.info("Запуск AI refine для wake-команды.")

            ai_result = pipeline.ai_gateway.refine_command_text(
                cleaned_text,
                rules={
                    "polite_words": nlu_resources.polite_words,
                    "filler_words": nlu_resources.filler_words,
                    "command_verbs": nlu_resources.command_verbs,
                    "extension_aliases": nlu_resources.extension_aliases,
                }
            )

            logger.info("AI refine wake-command result: %s", ai_result)

            if ai_result:
                if ai_result.get("normalized_text"):
                    final_text = ai_result["normalized_text"].strip()

                ai_intent_hint = self._normalize_ai_intent_hint(ai_result.get("intent_hint"))
                target_hint = ai_result.get("target_hint")
                entity_type_hint = ai_result.get("entity_type_hint")

                logger.info(
                    "Wake-команда после AI refine: %s | raw_intent_hint=%s | normalized_intent_hint=%s | target_hint=%s | entity_type_hint=%s | confidence=%s",
                    final_text,
                    ai_result.get("intent_hint"),
                    ai_intent_hint,
                    target_hint,
                    entity_type_hint,
                    ai_result.get("confidence"),
                )

        command = pipeline.parser.parse(final_text)
        parser_intent = command.intent

        logger.info("Wake parser returned intent=%s target=%s", command.intent, command.target_text)

        special_parser_intents = {
            "enable_chat_mode",
            "disable_chat_mode",
            "enable_dictation",
            "disable_dictation",
            "select_candidate",
            "confirm_deep_search",
            "reject_deep_search",
            "custom_command",
            "negative_feedback",
        }

        target_override_allowed_intents = {
            "generic_open",
            "open_file",
            "open_folder",
            "search_web",
            "search_youtube",
            "play_music_query",
        }

        if parser_intent in special_parser_intents:
            logger.info("AI override пропущен для wake-команды: parser уже распознал special intent=%s", parser_intent)
        else:
            if ai_intent_hint:
                logger.info("Применяю AI intent_hint=%s вместо parser intent=%s", ai_intent_hint, parser_intent)
                command.intent = ai_intent_hint

            if target_hint and command.intent in target_override_allowed_intents:
                logger.info("Применяю AI target_hint=%s", target_hint)
                command.target_text = str(target_hint).strip()

        logger.info("WAKE PARSED intent=%s target=%s", command.intent, command.target_text)
        print(f"[PARSED] intent={command.intent}, target={command.target_text}")

        if runtime_control.is_cancelled():
            logger.info("Wake-команда отменена пользователем после parse.")
            self.notifier.say("Операция отменена.")
            return None

        if command.intent == "select_candidate":
            try:
                return pipeline._handle_selection(int(command.target_text))
            except Exception:
                self.notifier.say("Не удалось выбрать вариант.")
                return None

        if command.intent == "confirm_deep_search":
            pending = session_state.pending_deep_search_command
            if pending is None:
                logger.info("Нет запроса на глубокий поиск.")
                self.notifier.say("Нет запроса на глубокий поиск.")
                return None
            return pipeline._handle_command(pending, deep_search=True)

        if command.intent == "reject_deep_search":
            return pipeline._handle_command(command, deep_search=False)

        return pipeline._handle_command(command, deep_search=False)

    def _request_activation(self, source: str, initial_text: str | None = None):
        if self.is_paused:
            logger.info("Команда проигнорирована: ассистент на паузе. source=%s", source)
            self.notifier.say("Ассистент на паузе.")
            return False

        if not self._is_microphone_allowed():
            logger.info("Команда проигнорирована: микрофон отключён. source=%s", source)
            print("[BG] Команда проигнорирована: микрофон отключён в настройках.")
            self.notifier.say("Микрофон отключён. Включите его во вкладке Аудио.")
            return False

        if self.is_busy():
            if source == "hotkey" and self.cancel_on_second_press:
                logger.info("Запрошена отмена текущей операции.")
                print("[BG] Запрошена отмена текущей операции.")

                runtime_control.cancel_job()

                if self.pipeline is not None:
                    self.pipeline.cancel_current_operation()

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
                if source == "voice":
                    logger.info("Голосовая активация сработала. initial_text=%r", initial_text)
                    print("[BG] Голосовая активация сработала.")
                else:
                    logger.info("Горячая клавиша нажата. Слушаю команду...")
                    print("[BG] Горячая клавиша нажата. Слушаю команду...")

                self._beep()

                pipeline = self._get_pipeline()

                if initial_text:
                    self._run_recognized_text_directly(pipeline, initial_text)
                else:
                    pipeline.run_once()

            except Exception as e:
                logger.exception("Ошибка во время выполнения команды: %s", e)
                print(f"[BG][ERROR] Ошибка во время выполнения команды: {e}")
                self.notifier.say("Произошла ошибка во время выполнения команды.")
            finally:
                runtime_control.finish_job()

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
        return True

    def _on_activate(self):
        # Hotkey остаётся рабочим всегда как запасной способ,
        # даже если в настройках выбран режим "По голосу".
        self._request_activation(source="hotkey")

    def _extract_command_after_wake(self, text: str) -> str | None:
        phrase = _normalize_wake_text(self.voice_activation_phrase)
        recognized = _normalize_wake_text(text)

        if not phrase or not recognized:
            return None

        if phrase not in recognized:
            return None

        after = recognized.split(phrase, 1)[1].strip()

        if not after:
            return ""

        return after

    def _wake_phrase_matches(self, text: str) -> bool:
        return self._extract_command_after_wake(text) is not None

    def _wake_worker(self, stop_event: threading.Event):
        logger.info(
            "Wake-listener запущен. phrase=%r record_seconds=%.2f interval=%.2f",
            self.voice_activation_phrase,
            self.wake_record_seconds,
            self.wake_check_interval_sec,
        )

        last_error_log_time = 0.0

        while not stop_event.is_set():
            try:
                if self.activation_mode != "voice":
                    break

                if self.is_paused or self.is_busy() or not self._is_microphone_allowed():
                    stop_event.wait(0.5)
                    continue

                wav_path = None

                try:
                    wav_path = record_wake_audio_to_wav(self.wake_record_seconds)

                    pipeline = self._get_pipeline()
                    stt_result = pipeline.transcriber.transcribe(wav_path)

                    logger.debug("Wake STT: %r", stt_result.text)

                    command_after_wake = self._extract_command_after_wake(stt_result.text)

                    if command_after_wake is not None:
                        logger.info(
                            "Wake-фраза распознана: text=%r command_after_wake=%r",
                            stt_result.text,
                            command_after_wake,
                        )
                        print(f"[BG] Wake-фраза распознана: {stt_result.text}")

                        if command_after_wake:
                            self._request_activation(source="voice", initial_text=command_after_wake)
                        else:
                            self._request_activation(source="voice")

                        stop_event.wait(1.0)

                except NoSpeechDetected:
                    pass

                except (MicrophoneSelectionError, NoMicrophoneSignalError) as e:
                    now = time.time()
                    if now - last_error_log_time > 10:
                        logger.warning("Wake-listener: проблема микрофона: %s", e)
                        last_error_log_time = now
                    stop_event.wait(1.0)

                except Exception as e:
                    now = time.time()
                    if now - last_error_log_time > 10:
                        logger.exception("Wake-listener: ошибка: %s", e)
                        last_error_log_time = now
                    stop_event.wait(1.0)

                finally:
                    if wav_path:
                        delete_temp_file(wav_path)

                stop_event.wait(self.wake_check_interval_sec)

            except Exception as e:
                logger.exception("Wake-listener: внешняя ошибка цикла: %s", e)
                stop_event.wait(1.0)

        logger.info("Wake-listener остановлен.")

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
            self._on_activate
        )
        like_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<alt>+<up>"),
            self._on_like
        )
        dislike_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<alt>+<down>"),
            self._on_dislike
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

        self._restart_listener()
        self._sync_wake_listener()

        logger.info(
            "Фоновый сервис запущен. Hotkey: %s activation_mode=%s wake_phrase=%r",
            self.hotkey,
            self.activation_mode,
            self.voice_activation_phrase,
        )
        print(f"[BG] Фоновый режим запущен. Горячая клавиша: {self.hotkey}")
        print(f"[BG] Режим активации: {self.activation_mode}")
        print("[BG] Лайк: Ctrl+Alt+Up | Дизлайк: Ctrl+Alt+Down")
        print("[BG] Повторное нажатие hotkey во время работы мгновенно отменяет текущую операцию.")

    def stop(self):
        self._stop_wake_listener()

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