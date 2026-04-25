import re

from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text
from app.custom_commands.admin import CustomCommandsAdmin
from app.settings_service import settings_service
from app.logger import get_logger

logger = get_logger("parser")


def normalize_phrase_for_match(text: str) -> str:
    text = normalize_command_text(text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text


class CommandParser:
    OPEN_FILE_KEYWORDS = [
        "открой файл", "открыть файл", "открою файл",
        "покажи файл", "показать файл"
    ]

    OPEN_FOLDER_KEYWORDS = [
        "открой папку", "открыть папку", "открою папку",
        "покажи папку", "показать папку"
    ]

    PLAY_MEDIA_KEYWORDS = [
        "включи песню", "включить песню",
        "включи музыку", "включить музыку",
        "воспроизведи"
    ]

    VIDEO_SEARCH_KEYWORDS = [
        "включи видео",
        "включить видео",
        "найди видео",
        "найти видео",
        "открой видео",
        "запусти видео"
    ]

    WEB_SEARCH_KEYWORDS = [
        "найди в браузере", "поиск в браузере", "найди в интернете", "найди в гугле"
    ]

    YOUTUBE_SEARCH_KEYWORDS = [
        "найди на ютубе", "найди в ютубе", "поиск на ютубе", "открой на ютубе"
    ]

    GENERIC_OPEN_KEYWORDS = [
        "открой", "открыть", "открою",
        "запусти", "запустить", "запущу",
        "включи", "включить",
        "покажи", "показать"
    ]

    NEGATIVE_FEEDBACK_KEYWORDS = [
        "ты ошибся",
        "не то",
        "не тот",
        "ошибка",
        "неправильно"
    ]

    DEEP_SEARCH_CONFIRM_KEYWORDS = [
        "да", "ищи", "ищи глубже", "ищи везде", "выполни глубокий поиск", "глубокий поиск"
    ]

    DEEP_SEARCH_REJECT_KEYWORDS = [
        "нет", "не ищи", "не надо", "отмена", "не нужно"
    ]

    DICTATION_ENABLE_KEYWORDS = [
        "включи диктовку",
        "включить диктовку",
        "режим диктовки",
        "начни диктовку",
        "начать диктовку",
        "включи режим диктовки",
        "включить режим диктовки"
    ]

    DICTATION_DISABLE_KEYWORDS = [
        "выключи диктовку",
        "выключить диктовку",
        "останови диктовку",
        "остановить диктовку",
        "заверши диктовку",
        "закончить диктовку",
        "выключи режим диктовки",
        "выключить режим диктовки"
    ]

    SELECTION_KEYWORDS = {
        "первый": 1, "первая": 1, "1": 1, "один": 1,
        "второй": 2, "вторая": 2, "2": 2, "два": 2,
        "третий": 3, "третья": 3, "3": 3, "три": 3,
    }

    TARGET_FILLER_WORDS = {
        "приложение", "приложения",
        "программа", "программу", "программы"
    }

    DEFAULT_WAKE_PHRASES = {
        "ассистент",
        "режим общения",
        "включи режим общения",
        "давай поговорим",
    }

    DEFAULT_STOP_PHRASES = {
        "выключи режим общения",
        "хватит общаться",
        "режим общения выключить",
        "заверши общение",
    }

    def __init__(self):
        self.custom_admin = CustomCommandsAdmin()

    def _cleanup_target(self, target: str) -> str:
        tokens = target.split()
        tokens = [t for t in tokens if t not in self.TARGET_FILLER_WORDS]
        return " ".join(tokens).strip()

    def _fallback_intent(self, normalized: str) -> ParsedCommand:
        words = normalized.split()

        if 1 <= len(words) <= 3:
            logger.info("PARSER fallback -> generic_open | normalized=%s", normalized)
            return ParsedCommand(normalized, normalized, "generic_open", normalized)

        if 3 <= len(words) <= 6:
            logger.info("PARSER fallback -> search_web | normalized=%s", normalized)
            return ParsedCommand(normalized, normalized, "search_web", normalized)

        logger.info("PARSER fallback -> unknown | normalized=%s", normalized)
        return ParsedCommand(normalized, normalized, "unknown", normalized)

    def _get_wake_phrases(self) -> set[str]:
        ai_cfg = settings_service.get_section("ai", {})
        raw = ai_cfg.get("wake_phrases", [])
        if not raw:
            raw = list(self.DEFAULT_WAKE_PHRASES)
        return {normalize_phrase_for_match(p) for p in raw if p}

    def _get_stop_phrases(self) -> set[str]:
        ai_cfg = settings_service.get_section("ai", {})
        raw = ai_cfg.get("stop_phrases", [])
        if not raw:
            raw = list(self.DEFAULT_STOP_PHRASES)
        return {normalize_phrase_for_match(p) for p in raw if p}

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)
        normalized_for_match = normalize_phrase_for_match(text)

        wake_phrases = self._get_wake_phrases()
        stop_phrases = self._get_stop_phrases()

        logger.info(
            "PARSER input | raw=%r | normalized=%r | normalized_for_match=%r",
            text,
            normalized,
            normalized_for_match,
        )
        logger.info("PARSER wake_phrases=%s", sorted(wake_phrases))
        logger.info("PARSER stop_phrases=%s", sorted(stop_phrases))

        custom = self.custom_admin.resolve_command(normalized)
        if custom and custom["is_enabled"]:
            logger.info("PARSER matched custom_command")
            return ParsedCommand(text, normalized, "custom_command", normalized)

        if normalized in self.SELECTION_KEYWORDS:
            logger.info("PARSER matched select_candidate")
            return ParsedCommand(text, normalized, "select_candidate", str(self.SELECTION_KEYWORDS[normalized]))

        if normalized_for_match in wake_phrases:
            logger.info("PARSER matched enable_chat_mode")
            return ParsedCommand(text, normalized, "enable_chat_mode", "")

        if normalized_for_match in stop_phrases:
            logger.info("PARSER matched disable_chat_mode")
            return ParsedCommand(text, normalized, "disable_chat_mode", "")

        if normalized in self.DICTATION_ENABLE_KEYWORDS:
            logger.info("PARSER matched enable_dictation")
            return ParsedCommand(text, normalized, "enable_dictation", "")

        if normalized in self.DICTATION_DISABLE_KEYWORDS:
            logger.info("PARSER matched disable_dictation")
            return ParsedCommand(text, normalized, "disable_dictation", "")

        if normalized in self.DEEP_SEARCH_CONFIRM_KEYWORDS:
            logger.info("PARSER matched confirm_deep_search")
            return ParsedCommand(text, normalized, "confirm_deep_search", "")

        if normalized in self.DEEP_SEARCH_REJECT_KEYWORDS:
            logger.info("PARSER matched reject_deep_search")
            return ParsedCommand(text, normalized, "reject_deep_search", "")

        for phrase in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if normalized == phrase or normalized.startswith(phrase):
                logger.info("PARSER matched negative_feedback")
                return ParsedCommand(text, normalized, "negative_feedback", "")

        for prefix in self.WEB_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                logger.info("PARSER matched search_web | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "search_web", target)

        for prefix in self.YOUTUBE_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                logger.info("PARSER matched search_youtube | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "search_youtube", target)

        for prefix in self.VIDEO_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info("PARSER matched video->search_youtube | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "search_youtube", target)

        for prefix in self.OPEN_FILE_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info("PARSER matched open_file | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "open_file", target)

        for prefix in self.OPEN_FOLDER_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info("PARSER matched open_folder | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "open_folder", target)

        for prefix in self.PLAY_MEDIA_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info("PARSER matched play_music_query | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "play_music_query", target)

        for prefix in self.GENERIC_OPEN_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info("PARSER matched generic_open | prefix=%s | target=%s", prefix, target)
                return ParsedCommand(text, normalized, "generic_open", target)

        return self._fallback_intent(normalized)