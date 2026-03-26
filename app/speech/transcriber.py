from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE
from app.models import STTResult


class SpeechTranscriber:
    def __init__(self):
        self.model = WhisperModel(
            WHISPER_MODEL_SIZE,
            compute_type=WHISPER_COMPUTE_TYPE
        )

    def transcribe(self, wav_path: str) -> STTResult:
        segments, info = self.model.transcribe(
            wav_path,
            beam_size=5,
            language=None  # пусть модель сама определяет
        )

        text = " ".join(segment.text.strip() for segment in segments).strip()
        return STTResult(text=text, language=getattr(info, "language", None))