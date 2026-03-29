import threading
from pynput import keyboard

from app.assistant_pipeline import AssistantPipeline
from app.config import BACKGROUND_SETTINGS


def run_background_mode():
    pipeline = AssistantPipeline()
    hotkey = BACKGROUND_SETTINGS.get("hotkey", "<ctrl>+<alt>+<space>")
    busy_lock = threading.Lock()

    def on_activate():
        if busy_lock.locked():
            print("[BG] Ассистент уже обрабатывает предыдущую команду.")
            return

        def worker():
            with busy_lock:
                print("[BG] Горячая клавиша нажата. Слушаю команду...")
                try:
                    pipeline.run_once()
                except Exception as e:
                    print(f"[BG][ERROR] Ошибка во время выполнения команды: {e}")

        threading.Thread(target=worker, daemon=True).start()

    try:
        hotkey_obj = keyboard.HotKey(
            keyboard.HotKey.parse(hotkey),
            on_activate
        )
    except ValueError as e:
        print(f"[BG][ERROR] Неверный формат горячей клавиши: {hotkey}")
        print(f"[BG][ERROR] Детали: {e}")
        return

    def on_press(key):
        hotkey_obj.press(listener.canonical(key))
        if key == keyboard.Key.esc:
            return False

    def on_release(key):
        hotkey_obj.release(listener.canonical(key))

    print(f"[BG] Фоновый режим запущен. Горячая клавиша: {hotkey}")
    print("[BG] Нажми ESC для выхода.")

    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    ) as listener:
        listener.join()