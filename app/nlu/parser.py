from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text


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

    SELECTION_KEYWORDS = {
        "первый": 1, "первая": 1, "1": 1, "один": 1,
        "второй": 2, "вторая": 2, "2": 2, "два": 2,
        "третий": 3, "третья": 3, "3": 3, "три": 3,
    }

    TARGET_FILLER_WORDS = {
        "приложение", "приложения",
        "программа", "программу", "программы"
    }

    def _cleanup_target(self, target: str) -> str:
        tokens = target.split()
        tokens = [t for t in tokens if t not in self.TARGET_FILLER_WORDS]
        return " ".join(tokens).strip()

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)

        if normalized in self.SELECTION_KEYWORDS:
            return ParsedCommand(text, normalized, "select_candidate", str(self.SELECTION_KEYWORDS[normalized]))

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

        return ParsedCommand(text, normalized, "unknown", normalized)