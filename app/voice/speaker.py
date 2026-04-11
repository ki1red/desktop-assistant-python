import os
import queue
import random
import subprocess
import threading

from app.config import VOICE_SETTINGS


class VoiceSpeaker:
    def __init__(self):
        self.enabled = VOICE_SETTINGS.get("enabled", True)
        self.rate = VOICE_SETTINGS.get("rate", 185)
        self.volume = VOICE_SETTINGS.get("volume", 1.0)

        self._queue = queue.Queue()
        self._thread = None
        self._started = False

        if self.enabled:
            self._start_worker()

    def _start_worker(self):
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _escape_powershell_text(self, text: str) -> str:
        return text.replace("'", "''")

    def _build_ps_script(self, text: str) -> str:
        escaped = self._escape_powershell_text(text)

        # Volume в System.Speech: 0..100
        volume_100 = int(max(0.0, min(1.0, self.volume)) * 100)

        # Rate в System.Speech: примерно -10..10
        # 185 считаем базой, приводим грубо
        ps_rate = int((self.rate - 185) / 12)
        ps_rate = max(-10, min(10, ps_rate))

        return f"""
Add-Type -AssemblyName System.Speech;
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
$synth.Volume = {volume_100};
$synth.Rate = {ps_rate};
$synth.Speak('{escaped}');
"""

    def _speak_windows(self, text: str):
        script = self._build_ps_script(text)

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                script
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )

    def _speak_platform(self, text: str):
        if os.name == "nt":
            self._speak_windows(text)
        else:
            # fallback: просто ничего не делаем, можно потом расширить
            pass

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
                self._speak_platform(text)
            except Exception as e:
                print(f"[VOICE][ERROR] Ошибка TTS: {e}")

    def say(self, text: str):
        if not self.enabled or not text:
            return
        self._queue.put(text)

    def say_sync(self, text: str):
        if not self.enabled or not text:
            return

        print(f"[VOICE] {text}")
        try:
            self._speak_platform(text)
        except Exception as e:
            print(f"[VOICE][ERROR] Ошибка TTS: {e}")

    def say_random(self, group_name: str):
        if not self.enabled:
            return

        phrases = VOICE_SETTINGS.get("phrases", {}).get(group_name, [])
        if not phrases:
            return

        self.say(random.choice(phrases))

    def say_random_sync(self, group_name: str):
        if not self.enabled:
            return

        phrases = VOICE_SETTINGS.get("phrases", {}).get(group_name, [])
        if not phrases:
            return

        self.say_sync(random.choice(phrases))


speaker = VoiceSpeaker()