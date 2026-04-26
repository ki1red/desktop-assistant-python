import re
from dataclasses import dataclass

from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE
from app.settings_service import settings_service
from app.logger import get_logger


logger = get_logger("transcriber")


class NoSpeechDetected(ValueError):
    """
    Нормальная пользовательская ситуация:
    запись была сделана, но Whisper не смог выделить речь.

    Это не авария приложения, поэтому pipeline должен обрабатывать
    это отдельно от настоящих исключений.
    """
    pass


@dataclass
class STTResult:
    text: str
    language: str | None = None


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _looks_bad_for_command(text: str) -> bool:
    """
    Простая эвристика для коротких команд:
    если Whisper вернул слишком короткий/странный текст,
    даём шанс fallback-распознаванию.
    """
    t = _normalize_spaces(text).lower()
    if not t:
        return True

    bad_exact = {
        "thank you",
        "thanks",
        "yeah",
        "yes",
        "no",
        "okay",
        "ok",
    }
    if t in bad_exact:
        return True

    has_cyrillic = bool(re.search(r"[а-яё]", t))
    if len(t) <= 4 and not has_cyrillic:
        return True

    return False


class SpeechTranscriber:
    def __init__(self):
        logger.info(
            "Инициализация WhisperModel: model=%s compute_type=%s",
            WHISPER_MODEL_SIZE,
            WHISPER_COMPUTE_TYPE
        )

        self.model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
        )

        logger.info("WhisperModel инициализирован.")

    def _transcribe_once(self, wav_path: str, language: str | None) -> STTResult:
        segments_iter, info = self.model.transcribe(
            wav_path,
            beam_size=5,
            vad_filter=True,
            language=language,
            condition_on_previous_text=False,
        )

        segments = list(segments_iter)
        text = _normalize_spaces(" ".join(seg.text for seg in segments))
        detected_language = getattr(info, "language", None)

        logger.info(
            "STT pass: language=%s result=%r segments=%s wav=%r",
            language,
            text,
            len(segments),
            wav_path
        )

        return STTResult(
            text=text,
            language=detected_language
        )

    def transcribe(self, wav_path: str) -> STTResult:
        speech_cfg = settings_service.get_section("speech", {})

        preferred_language = speech_cfg.get("command_language", "ru")
        fallback_to_auto = speech_cfg.get("fallback_to_auto_language", True)

        first = self._transcribe_once(wav_path, preferred_language)
        result = first

        if fallback_to_auto and _looks_bad_for_command(first.text):
            second = self._transcribe_once(wav_path, None)

            if not _looks_bad_for_command(second.text):
                result = second

        result.text = _normalize_spaces(result.text)

        if not result.text:
            logger.warning(
                "STT empty result: wav=%r preferred_language=%r fallback_to_auto=%s",
                wav_path,
                preferred_language,
                fallback_to_auto
            )
            raise NoSpeechDetected(f"Речь не распознана в файле: {wav_path}")

        logger.info("STT final: %r", result.text)
        return result