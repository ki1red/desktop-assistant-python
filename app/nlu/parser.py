from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text
from app.custom_commands.admin import CustomCommandsAdmin
from app.settings_service import settings_service


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
        "ты ошибся", "не то", "не это",
        "не тот файл", "не та папка",
        "ошибка", "неправильно"
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

    def __init__(self):
        self.custom_admin = CustomCommandsAdmin()

    def _cleanup_target(self, target: str) -> str:
        tokens = target.split()
        tokens = [t for t in tokens if t not in self.TARGET_FILLER_WORDS]
        return " ".join(tokens).strip()

    def _fallback_intent(self, normalized: str) -> ParsedCommand:
        words = normalized.split()

        if 1 <= len(words) <= 3:
            return ParsedCommand(normalized, normalized, "generic_open", normalized)

        if 3 <= len(words) <= 6:
            return ParsedCommand(normalized, normalized, "search_web", normalized)

        return ParsedCommand(normalized, normalized, "unknown", normalized)

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)

        ai_cfg = settings_service.get_section("ai", {})
        wake_phrases = set(ai_cfg.get("wake_phrases", []))
        stop_phrases = set(ai_cfg.get("stop_phrases", []))

        custom = self.custom_admin.resolve_command(normalized)
        if custom and custom["is_enabled"]:
            return ParsedCommand(text, normalized, "custom_command", normalized)

        if normalized in self.SELECTION_KEYWORDS:
            return ParsedCommand(text, normalized, "select_candidate", str(self.SELECTION_KEYWORDS[normalized]))

        if normalized in wake_phrases:
            return ParsedCommand(text, normalized, "enable_chat_mode", "")

        if normalized in stop_phrases:
            return ParsedCommand(text, normalized, "disable_chat_mode", "")

        if normalized in self.DICTATION_ENABLE_KEYWORDS:
            return ParsedCommand(text, normalized, "enable_dictation", "")

        if normalized in self.DICTATION_DISABLE_KEYWORDS:
            return ParsedCommand(text, normalized, "disable_dictation", "")

        if normalized in self.DEEP_SEARCH_CONFIRM_KEYWORDS:
            return ParsedCommand(text, normalized, "confirm_deep_search", "")

        if normalized in self.DEEP_SEARCH_REJECT_KEYWORDS:
            return ParsedCommand(text, normalized, "reject_deep_search", "")

        for phrase in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if normalized == phrase or normalized.startswith(phrase):
                return ParsedCommand(text, normalized, "negative_feedback", "")

        for prefix in self.WEB_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, "search_web", target)

        for prefix in self.YOUTUBE_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, "search_youtube", target)

        for prefix in self.VIDEO_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                return ParsedCommand(text, normalized, "search_youtube", target)

        for prefix in self.OPEN_FILE_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                return ParsedCommand(text, normalized, "open_file", target)

        for prefix in self.OPEN_FOLDER_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                return ParsedCommand(text, normalized, "open_folder", target)

        for prefix in self.PLAY_MEDIA_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                return ParsedCommand(text, normalized, "play_music_query", target)

        for prefix in self.GENERIC_OPEN_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                return ParsedCommand(text, normalized, "generic_open", target)

        return self._fallback_intent(normalized)