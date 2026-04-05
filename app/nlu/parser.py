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

        for phrase in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if normalized == phrase or normalized.startswith(phrase):
                return ParsedCommand(text, normalized, "negative_feedback", "")

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
                return ParsedCommand(text, normalized, "play_media", target)

        for prefix in self.GENERIC_OPEN_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                return ParsedCommand(text, normalized, "generic_open", target)

        return ParsedCommand(text, normalized, "unknown", normalized)