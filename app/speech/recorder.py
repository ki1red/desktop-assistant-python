import os
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.config import TEMP_DIR, TEMP_CLEANUP_SETTINGS
from app.settings_service import settings_service


def _make_temp_filename() -> str:
    ts = int(time.time())
    return str(TEMP_DIR / f"command_{ts}.wav")


def _rms_int16(chunk: np.ndarray) -> float:
    if chunk.size == 0:
        return 0.0
    audio = chunk.astype(np.float32)
    return float(np.sqrt(np.mean(np.square(audio))))


def record_audio_to_wav():
    audio_cfg = settings_service.get_section("audio", {})

    sample_rate = audio_cfg.get("sample_rate", 16000)
    channels = audio_cfg.get("channels", 1)
    chunk_size = audio_cfg.get("chunk_size", 1024)
    max_record_seconds = audio_cfg.get("max_record_seconds", 12)
    min_record_seconds = audio_cfg.get("min_record_seconds", 0.8)
    silence_duration_stop_sec = audio_cfg.get("silence_duration_stop_sec", 1.0)
    silence_threshold = audio_cfg.get("silence_threshold", 500)

    output_path = _make_temp_filename()

    print("[REC] Запись до паузы...")
    frames = []

    silence_started_at = None
    started_at = time.time()
    silence_detection_enabled_after = 1.0

    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        blocksize=chunk_size
    ) as stream:
        while True:
            data, _overflowed = stream.read(chunk_size)
            frames.append(data.copy())

            now = time.time()
            elapsed = now - started_at
            rms = _rms_int16(data)

            if elapsed >= silence_detection_enabled_after:
                if rms >= silence_threshold:
                    silence_started_at = None
                else:
                    if silence_started_at is None:
                        silence_started_at = now

                if elapsed >= min_record_seconds and silence_started_at is not None:
                    silent_for = now - silence_started_at
                    if silent_for >= silence_duration_stop_sec:
                        break

            if elapsed >= max_record_seconds:
                break

    audio = np.concatenate(frames, axis=0)

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())

    print(f"[REC] Сохранено: {output_path}")
    return output_path


def delete_temp_file(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"[TEMP][WARN] Не удалось удалить временный файл {path}: {e}")


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