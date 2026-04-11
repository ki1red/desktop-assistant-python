import os
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.config import (
    TEMP_DIR,
    TEMP_CLEANUP_SETTINGS,
    AUDIO_SAMPLE_RATE,
    AUDIO_CHANNELS,
    AUDIO_CHUNK_SIZE,
    MAX_RECORD_SECONDS,
    MIN_RECORD_SECONDS,
    SILENCE_DURATION_STOP_SEC,
    SILENCE_THRESHOLD,
)


def _make_temp_filename() -> str:
    ts = int(time.time())
    return str(TEMP_DIR / f"command_{ts}.wav")


def _rms_int16(chunk: np.ndarray) -> float:
    if chunk.size == 0:
        return 0.0
    audio = chunk.astype(np.float32)
    return float(np.sqrt(np.mean(np.square(audio))))


def record_audio_to_wav():
    output_path = _make_temp_filename()

    print("[REC] Запись до паузы...")
    frames = []

    silence_started_at = None
    started_at = time.time()
    silence_detection_enabled_after = 1.0  # начинаем искать паузу только через 1 секунду

    with sd.InputStream(
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="int16",
        blocksize=AUDIO_CHUNK_SIZE
    ) as stream:
        while True:
            data, _overflowed = stream.read(AUDIO_CHUNK_SIZE)
            frames.append(data.copy())

            now = time.time()
            elapsed = now - started_at

            rms = _rms_int16(data)

            # До первой секунды паузу вообще не анализируем
            if elapsed >= silence_detection_enabled_after:
                if rms >= SILENCE_THRESHOLD:
                    silence_started_at = None
                else:
                    if silence_started_at is None:
                        silence_started_at = now

                if elapsed >= MIN_RECORD_SECONDS and silence_started_at is not None:
                    silent_for = now - silence_started_at
                    if silent_for >= SILENCE_DURATION_STOP_SEC:
                        break

            if elapsed >= MAX_RECORD_SECONDS:
                break

    audio = np.concatenate(frames, axis=0)

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    print(f"[REC] Сохранено: {output_path}")
    return output_path


def delete_temp_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"[TEMP][WARN] Не удалось удалить временный файл {path}: {e}")

import time
from pathlib import Path

from app.config import TEMP_DIR, TEMP_CLEANUP_SETTINGS

def cleanup_old_temp_files():
    if not TEMP_CLEANUP_SETTINGS.get("delete_old_temp_on_startup", True):
        return

    max_age_hours = TEMP_CLEANUP_SETTINGS.get("max_temp_age_hours", 24)
    max_age_seconds = max_age_hours * 3600
    now = time.time()

    for path in Path(TEMP_DIR).glob("command_*.wav"):
        try:
            file_age = now - path.stat().st_mtime
            if file_age >= max_age_seconds:
                path.unlink(missing_ok=True)
                print(f"[TEMP] Удалён старый временный файл: {path}")
        except Exception as e:
            print(f"[TEMP][WARN] Не удалось удалить {path}: {e}")