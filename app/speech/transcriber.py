import re
from dataclasses import dataclass

from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE
from app.settings_service import settings_service
from app.logger import get_logger

logger = get_logger("transcriber")


@dataclass
class STTResult:
    text: str
    language: str | None = None


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


class SpeechTranscriber:
    def __init__(self):
        self.model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
        )

    def _transcribe_once(self, wav_path: str, language: str | None) -> STTResult:
        try:
            segments, info = self.model.transcribe(
                wav_path,
                beam_size=1,
                language=language,
                vad_filter=False,
                condition_on_previous_text=False,
                task="transcribe",
            )

            segments = list(segments)
            text = " ".join(seg.text for seg in segments).strip()
            lang = getattr(info, "language", None)

            logger.info(
                "STT pass: language=%s result='%s' segments=%s wav='%s'",
                language,
                text,
                len(segments),
                wav_path,
            )

            return STTResult(
                text=_normalize_spaces(text),
                language=lang
            )
        except Exception as e:
            logger.exception(
                "STT internal error: language=%s wav='%s' error=%s",
                language,
                wav_path,
                e,
            )
            raise

    def transcribe(self, wav_path: str) -> STTResult:
        speech_cfg = settings_service.get_all().get("speech", {})
        preferred_language = speech_cfg.get("command_language", "ru")
        fallback_to_auto = speech_cfg.get("fallback_to_auto_language", True)

        # 1. Сначала принудительно русский язык
        result = self._transcribe_once(wav_path, preferred_language)
        if result.text:
            logger.info("STT final: '%s'", result.text)
            return result

        # 2. Потом автоопределение языка
        if fallback_to_auto:
            result_auto = self._transcribe_once(wav_path, None)
            if result_auto.text:
                logger.info("STT final: '%s'", result_auto.text)
                return result_auto

        raise ValueError(f"Пустой результат распознавания для файла: {wav_path}")