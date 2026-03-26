import time
from pathlib import Path

import sounddevice as sd
import soundfile as sf

from app.config import TEMP_DIR, AUDIO_SAMPLE_RATE, AUDIO_CHANNELS


def record_audio_to_wav(duration_sec: int = 5) -> str:
    """
    MVP-версия: просто записывает фиксированное количество секунд.
    Позже заменим на Silero VAD + остановку по тишине.
    """
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