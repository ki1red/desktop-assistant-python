import re
from dataclasses import dataclass

from faster_whisper import WhisperModel

from app.config import WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE
from app.settings_service import settings_service


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

    # типичные короткие англоязычные ложные срабатывания
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

    # слишком коротко и без кириллицы
    has_cyrillic = bool(re.search(r"[а-яё]", t))
    if len(t) <= 4 and not has_cyrillic:
        return True

    return False


class SpeechTranscriber:
    def __init__(self):
        self.model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=WHISPER_COMPUTE_TYPE,
        )

    def _transcribe_once(self, wav_path: str, language: str | None) -> STTResult:
        segments, info = self.model.transcribe(
            wav_path,
            beam_size=5,
            vad_filter=True,
            language=language,
            condition_on_previous_text=False,
        )

        text = " ".join(seg.text for seg in segments).strip()
        return STTResult(text=text, language=getattr(info, "language", None))

    def transcribe(self, wav_path: str) -> STTResult:
        speech_cfg = settings_service.get_section("speech", {})
        preferred_language = speech_cfg.get("command_language", "ru")
        fallback_to_auto = speech_cfg.get("fallback_to_auto_language", True)

        # 1. Сначала пробуем как русскую команду
        first = self._transcribe_once(wav_path, preferred_language)

        if not fallback_to_auto:
            return first

        # 2. Если результат подозрительный — fallback на auto
        if _looks_bad_for_command(first.text):
            second = self._transcribe_once(wav_path, None)

            # если auto дал что-то осмысленнее — берём его
            if not _looks_bad_for_command(second.text):
                return second

        return first