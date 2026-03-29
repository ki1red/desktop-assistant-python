from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text


class CommandParser:
    OPEN_FILE_KEYWORDS = ["открой файл", "открыть файл", "покажи файл"]
    OPEN_FOLDER_KEYWORDS = ["открой папку", "открыть папку", "покажи папку"]
    PLAY_MEDIA_KEYWORDS = ["включи песню", "включить песню", "включи музыку", "воспроизведи"]

    GENERIC_OPEN_KEYWORDS = [
        "открой", "открыть", "запусти", "запустить", "включи", "включить", "покажи"
    ]

    NEGATIVE_FEEDBACK_KEYWORDS = [
        "ты ошибся", "не то", "не это", "не тот файл", "не та папка", "ошибка", "неправильно"
    ]

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)

        for phrase in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if normalized == phrase or normalized.startswith(phrase):
                return ParsedCommand(text, normalized, "negative_feedback", "")

        for prefix in self.OPEN_FILE_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, "open_file", target)

        for prefix in self.OPEN_FOLDER_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, "open_folder", target)

        for prefix in self.PLAY_MEDIA_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, "play_media", target)

        for prefix in self.GENERIC_OPEN_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, "generic_open", target)

        return ParsedCommand(text, normalized, "unknown", normalized)