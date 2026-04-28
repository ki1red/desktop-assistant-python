import os
import queue
import random
import subprocess
import threading
import time

from app.settings_service import settings_service
from app.logger import get_logger


logger = get_logger("voice")


class VoiceSpeaker:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None
        self._started = False

        self._process_lock = threading.RLock()
        self._current_process = None

        self._generation_lock = threading.RLock()
        self._generation = 0

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

        if self.enabled:
            self._start_worker()
        else:
            self.stop(clear_queue=True)

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

    def _get_generation(self) -> int:
        with self._generation_lock:
            return self._generation

    def _bump_generation(self) -> int:
        with self._generation_lock:
            self._generation += 1
            return self._generation

    def _is_generation_current(self, generation: int) -> bool:
        with self._generation_lock:
            return generation == self._generation

    def _clear_queue(self):
        try:
            with self._queue.mutex:
                self._queue.queue.clear()
        except Exception:
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def _terminate_current_process(self):
        with self._process_lock:
            proc = self._current_process

        if proc is None:
            return

        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=0.8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=0.8)
        except Exception as e:
            logger.debug("Не удалось остановить TTS process: %s", e)
        finally:
            with self._process_lock:
                if self._current_process is proc:
                    self._current_process = None

    def stop(self, clear_queue: bool = True):
        """
        Мгновенно останавливает текущую озвучку и очищает очередь.

        Используется перед новой активацией ассистента, чтобы его голос
        не попадал в микрофон.
        """
        self._bump_generation()

        if clear_queue:
            self._clear_queue()

        self._terminate_current_process()
        logger.info("[VOICE] speech stopped")

    def is_speaking(self) -> bool:
        """
        Проверяет, говорит ли ассистент сейчас или есть ли очередь TTS.
        """
        with self._process_lock:
            proc = self._current_process
            if proc is not None and proc.poll() is None:
                return True

        return not self._queue.empty()

    def _speak_windows(self, text: str, generation: int):
        script = self._build_ps_script(text)

        startupinfo = None
        creationflags = 0

        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-Command",
                script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        with self._process_lock:
            self._current_process = proc

        try:
            while True:
                if not self._is_generation_current(generation):
                    try:
                        if proc.poll() is None:
                            proc.terminate()
                    except Exception:
                        pass
                    break

                if proc.poll() is not None:
                    break

                time.sleep(0.03)

            try:
                if proc.poll() is None:
                    proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=0.5)

        finally:
            with self._process_lock:
                if self._current_process is proc:
                    self._current_process = None

    def _speak_platform(self, text: str, generation: int):
        if os.name == "nt":
            self._speak_windows(text, generation)

    def _worker(self):
        while True:
            item = self._queue.get()

            if item is None:
                break

            if isinstance(item, tuple):
                generation, text = item
            else:
                generation = self._get_generation()
                text = item

            text = (text or "").strip()
            if not text:
                continue

            if not self.enabled:
                continue

            if not self._is_generation_current(generation):
                continue

            logger.info("[VOICE] %s", text)
            print(f"[VOICE] {text}")

            try:
                self._speak_platform(text, generation)
            except Exception as e:
                logger.exception("Ошибка TTS: %s", e)
                print(f"[VOICE][ERROR] Ошибка TTS: {e}")

    def say(self, text: str):
        if not self.enabled or not text:
            return

        self._start_worker()
        self._queue.put((self._get_generation(), text))

    def say_sync(self, text: str):
        if not self.enabled or not text:
            return

        self._start_worker()

        generation = self._get_generation()
        logger.info("[VOICE_SYNC] %s", text)
        print(f"[VOICE] {text}")

        try:
            self._speak_platform(text, generation)
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