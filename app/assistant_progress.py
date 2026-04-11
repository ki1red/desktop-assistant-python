import threading
import time

from app.config import VOICE_SETTINGS
from app.voice.speaker import speaker


class ProgressHeartbeat:
    def __init__(self):
        self.interval = VOICE_SETTINGS.get("heartbeat_interval_sec", 8)
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        time.sleep(self.interval)
        while not self._stop_event.is_set():
            speaker.say_random("working")
            time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()