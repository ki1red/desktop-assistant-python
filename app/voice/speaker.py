import queue
import random
import threading
import time

import pyttsx3

from app.config import VOICE_SETTINGS


class VoiceSpeaker:
    def __init__(self):
        self.enabled = VOICE_SETTINGS.get("enabled", True)
        self.rate = VOICE_SETTINGS.get("rate", 185)
        self.volume = VOICE_SETTINGS.get("volume", 1.0)

        self._queue = queue.Queue()
        self._thread = None
        self._engine = None
        self._started = False
        self._lock = threading.Lock()

        if self.enabled:
            self._start_worker()

    def _create_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        return engine

    def _start_worker(self):
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _ensure_engine(self):
        if self._engine is None:
            self._engine = self._create_engine()

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                break

            text = item.strip()
            if not text:
                continue

            print(f"[VOICE] {text}")

            try:
                with self._lock:
                    self._ensure_engine()
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception as e:
                print(f"[VOICE][ERROR] Ошибка TTS: {e}")
                try:
                    self._engine = None
                    time.sleep(0.2)
                    with self._lock:
                        self._ensure_engine()
                        self._engine.say(text)
                        self._engine.runAndWait()
                except Exception as e2:
                    print(f"[VOICE][ERROR] Повторная ошибка TTS: {e2}")
                    self._engine = None

    def say(self, text: str):
        if not self.enabled or not text:
            return
        self._queue.put(text)

    def say_random(self, group_name: str):
        if not self.enabled:
            return

        phrases = VOICE_SETTINGS.get("phrases", {}).get(group_name, [])
        if not phrases:
            return

        phrase = random.choice(phrases)
        self.say(phrase)


speaker = VoiceSpeaker()