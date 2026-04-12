import threading
from pynput import keyboard

from app.assistant_pipeline import AssistantPipeline
from app.session.state import session_state
from app.adaptive.history import register_negative_feedback, register_positive_feedback
from app.events.notifier import AssistantNotifier
from app.runtime_control import runtime_control
from app.logger import get_logger
from app.settings_service import settings_service


logger = get_logger("background_service")


class BackgroundAssistantService:
    def __init__(self):
        self.pipeline = AssistantPipeline()
        self.notifier = AssistantNotifier()
        self.listener = None
        self._running = False
        self.is_paused = False

        self.hotkey = "<ctrl>+<alt>+<space>"
        self.cancel_on_second_press = True

        self._apply_config(settings_service.get_all())
        settings_service.subscribe(self._on_settings_changed)

    def _apply_config(self, config_snapshot: dict):
        bg = config_snapshot.get("background", {})
        new_hotkey = bg.get("hotkey", "<ctrl>+<alt>+<space>")
        new_cancel = bg.get("double_press_cancels", True)

        hotkey_changed = new_hotkey != self.hotkey
        cancel_changed = new_cancel != self.cancel_on_second_press

        self.hotkey = new_hotkey
        self.cancel_on_second_press = new_cancel

        if self._running and (hotkey_changed or cancel_changed):
            logger.info("Настройки hotkey обновлены на лету: hotkey=%s cancel=%s", self.hotkey, self.cancel_on_second_press)
            self._restart_listener()

    def _on_settings_changed(self, config_snapshot: dict):
        self._apply_config(config_snapshot)

    def _beep(self):
        try:
            import winsound
            winsound.Beep(1200, 120)
        except Exception:
            pass

    def _on_activate(self):
        if self.is_paused:
            logger.info("Команда проигнорирована: ассистент на паузе.")
            self.notifier.say("Ассистент на паузе.")
            return

        if runtime_control.is_busy():
            if self.cancel_on_second_press:
                runtime_control.cancel_job()
                if runtime_control.mark_cancel_announced():
                    logger.info("Запрошена отмена текущей операции.")
                    print("[BG] Запрошена отмена текущей операции.")
                    self.notifier.say("Отменяю текущую операцию.")
            else:
                logger.info("Ассистент уже обрабатывает предыдущую команду.")
                print("[BG] Ассистент уже обрабатывает предыдущую команду.")
                self.notifier.say("Я ещё работаю.")
            return

        def worker():
            runtime_control.start_job()
            try:
                logger.info("Горячая клавиша нажата. Слушаю команду...")
                print("[BG] Горячая клавиша нажата. Слушаю команду...")
                self._beep()
                self.pipeline.run_once()
            except Exception as e:
                logger.exception("Ошибка во время выполнения команды: %s", e)
                print(f"[BG][ERROR] Ошибка во время выполнения команды: {e}")
                self.notifier.say("Произошла ошибка во время выполнения команды.")
            finally:
                runtime_control.finish_job()

        threading.Thread(target=worker, daemon=True).start()

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

    def start(self):
        if self._running:
            return

        self._restart_listener()
        self._running = True

        logger.info("Фоновый сервис запущен. Hotkey: %s", self.hotkey)
        print(f"[BG] Фоновый режим запущен. Горячая клавиша: {self.hotkey}")
        print("[BG] Лайк: Ctrl+Alt+Up | Дизлайк: Ctrl+Alt+Down")
        print("[BG] Повторное нажатие hotkey во время работы отменяет текущую операцию.")

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        self._running = False
        logger.info("Фоновый сервис остановлен.")