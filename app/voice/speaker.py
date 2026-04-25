import os
import queue
import random
import subprocess
import threading

from app.settings_service import settings_service
from app.logger import get_logger


logger = get_logger("voice")


class VoiceSpeaker:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None
        self._started = False

        self.enabled = True
        self.rate = 185
        self.volume = 1.0

        self._apply_config(settings_service.get_all())
        settings_service.subscribe(self._on_settings_changed)

        if self.enabled:
            self._start_worker()

    def _on_settings_changed(self, config_snapshot: dict):
        self._apply_config(config_snapshot)
        logger.info(
            "Голосовые настройки обновлены: enabled=%s rate=%s volume=%s",
            self.enabled, self.rate, self.volume
        )

    def _apply_config(self, config_snapshot: dict):
        voice = config_snapshot.get("voice", {})
        self.enabled = voice.get("enabled", True)
        self.rate = voice.get("rate", 185)
        self.volume = voice.get("volume", 1.0)

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
        volume_100 = int(max(0.0, min(1.0, self.volume)) * 100)
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

        startupinfo = None
        creationflags = 0

        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-Command",
                script
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

    def _speak_platform(self, text: str):
        if os.name == "nt":
            self._speak_windows(text)

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                break

            text = item.strip()
            if not text:
                continue

            if not self.enabled:
                continue

            logger.info("[VOICE] %s", text)
            print(f"[VOICE] {text}")

            try:
                self._speak_platform(text)
            except Exception as e:
                logger.exception("Ошибка TTS: %s", e)
                print(f"[VOICE][ERROR] Ошибка TTS: {e}")

    def say(self, text: str):
        if not self.enabled or not text:
            return
        self._queue.put(text)

    def say_sync(self, text: str):
        if not self.enabled or not text:
            return

        logger.info("[VOICE_SYNC] %s", text)
        print(f"[VOICE] {text}")
        try:
            self._speak_platform(text)
        except Exception as e:
            logger.exception("Ошибка TTS: %s", e)
            print(f"[VOICE][ERROR] Ошибка TTS: {e}")

    def say_random(self, group_name: str):
        if not self.enabled:
            return

        phrases = settings_service.get_section("voice", {}).get("phrases", {}).get(group_name, [])
        if not phrases:
            return

        self.say(random.choice(phrases))

    def say_random_sync(self, group_name: str):
        if not self.enabled:
            return

        phrases = settings_service.get_section("voice", {}).get("phrases", {}).get(group_name, [])
        if not phrases:
            return

        self.say_sync(random.choice(phrases))


speaker = VoiceSpeaker()