import os
import time
from pathlib import Path

import sounddevice as sd
import soundfile as sf

from app.config import TEMP_DIR, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, TEMP_CLEANUP_SETTINGS


def record_audio_to_wav(duration_sec: int = 5) -> str:
    filename = TEMP_DIR / f"command_{int(time.time())}.wav"

    print(f"[REC] Запись {duration_sec} сек...")
    audio = sd.rec(
        int(duration_sec * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="float32"
    )
    sd.wait()

    sf.write(str(filename), audio, AUDIO_SAMPLE_RATE)
    print(f"[REC] Сохранено: {filename}")
    return str(filename)


def delete_temp_file(file_path: str):
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def cleanup_old_temp_files():
    if not TEMP_CLEANUP_SETTINGS.get("delete_old_temp_on_startup", True):
        return

    max_age_hours = TEMP_CLEANUP_SETTINGS.get("max_temp_age_hours", 24)
    max_age_seconds = max_age_hours * 3600
    now = time.time()

    for item in Path(TEMP_DIR).glob("command_*.wav"):
        try:
            if now - item.stat().st_mtime > max_age_seconds:
                item.unlink(missing_ok=True)
        except OSError:
            continue