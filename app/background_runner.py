import threading
from pynput import keyboard

from app.assistant_pipeline import AssistantPipeline
from app.config import BACKGROUND_SETTINGS
from app.session.state import session_state
from app.adaptive.history import register_negative_feedback, register_positive_feedback
from app.events.notifier import AssistantNotifier
from app.runtime_control import runtime_control


def run_background_mode():
    pipeline = AssistantPipeline()
    notifier = AssistantNotifier()
    hotkey = BACKGROUND_SETTINGS.get("hotkey", "<ctrl>+<alt>+<space>")
    cancel_on_second_press = BACKGROUND_SETTINGS.get("double_press_cancels", True)

    def _beep():
        try:
            import winsound
            winsound.Beep(1200, 120)
        except Exception:
            pass

    def on_activate():
        if runtime_control.is_busy():
            if cancel_on_second_press:
                runtime_control.cancel_job()
                if runtime_control.mark_cancel_announced():
                    print("[BG] Запрошена отмена текущей операции.")
                    notifier.say("Отменяю текущую операцию.")
            else:
                print("[BG] Ассистент уже обрабатывает предыдущую команду.")
                notifier.say("Я ещё работаю.")
            return

        def worker():
            runtime_control.start_job()
            try:
                print("[BG] Горячая клавиша нажата. Слушаю команду...")
                _beep()
                pipeline.run_once()
            except Exception as e:
                print(f"[BG][ERROR] Ошибка во время выполнения команды: {e}")
                notifier.say("Произошла ошибка во время выполнения команды.")
            finally:
                runtime_control.finish_job()

        threading.Thread(target=worker, daemon=True).start()

    def on_like():
        last = session_state.last_resolved
        if last and last.target_path:
            register_positive_feedback(last.target_path)
            print(f"[BG] Лайк сохранён: {last.target_name}")
            notifier.say_random("like")
        else:
            print("[BG] Нет последней команды для лайка.")
            notifier.say("Нет последней команды для лайка.")

    def on_dislike():
        last = session_state.last_resolved
        if last and last.target_path:
            register_negative_feedback(last.target_path)
            print(f"[BG] Дизлайк сохранён: {last.target_name}")
            notifier.say_random("dislike")
        else:
            print("[BG] Нет последней команды для дизлайка.")
            notifier.say("Нет последней команды для дизлайка.")

    try:
        open_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(hotkey),
            on_activate
        )
        like_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<alt>+<up>"),
            on_like
        )
        dislike_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse("<ctrl>+<alt>+<down>"),
            on_dislike
        )
    except ValueError as e:
        print(f"[BG][ERROR] Ошибка формата hotkey: {e}")
        return

    def on_press(key):
        canonical = listener.canonical(key)
        open_hotkey.press(canonical)
        like_hotkey.press(canonical)
        dislike_hotkey.press(canonical)

        if key == keyboard.Key.esc:
            return False

    def on_release(key):
        canonical = listener.canonical(key)
        open_hotkey.release(canonical)
        like_hotkey.release(canonical)
        dislike_hotkey.release(canonical)

    print(f"[BG] Фоновый режим запущен. Горячая клавиша: {hotkey}")
    print("[BG] Лайк: Ctrl+Alt+Up | Дизлайк: Ctrl+Alt+Down")
    print("[BG] Повторное нажатие hotkey во время работы отменяет текущую операцию.")
    print("[BG] Нажми ESC для выхода.")

    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    ) as listener:
        listener.join()