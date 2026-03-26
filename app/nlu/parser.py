from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text


class CommandParser:
    OPEN_APP_KEYWORDS = ["запусти", "запустить", "включи", "включить", "открой", "открыть"]
    OPEN_FILE_KEYWORDS = ["открой файл", "открыть файл", "покажи файл"]
    OPEN_FOLDER_KEYWORDS = ["открой папку", "открыть папку", "покажи папку"]
    PLAY_MEDIA_KEYWORDS = ["включи песню", "включить песню", "включи музыку", "воспроизведи"]

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)

        intent = "unknown"
        target = normalized

        for prefix in self.OPEN_FILE_KEYWORDS:
            if normalized.startswith(prefix):
                intent = "open_file"
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, intent, target)

        for prefix in self.OPEN_FOLDER_KEYWORDS:
            if normalized.startswith(prefix):
                intent = "open_folder"
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, intent, target)

        for prefix in self.PLAY_MEDIA_KEYWORDS:
            if normalized.startswith(prefix):
                intent = "play_media"
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, intent, target)

        for prefix in self.OPEN_APP_KEYWORDS:
            if normalized.startswith(prefix):
                intent = "open_app"
                target = normalized.replace(prefix, "", 1).strip()
                return ParsedCommand(text, normalized, intent, target)

        return ParsedCommand(text, normalized, intent, target)