from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# Для старта можно medium или small.
# Если железо тянет, потом поменяешь на large-v3.
WHISPER_MODEL_SIZE = "medium"

# compute_type:
# "int8" - хорошо для CPU
# "float16" - обычно для GPU
WHISPER_COMPUTE_TYPE = "int8"

# Пороги fuzzy matching
APP_MATCH_THRESHOLD = 70
FILE_MATCH_THRESHOLD = 65

# Расширения, которые будем считать "файлами документов/медиа"
KNOWN_FILE_EXTENSIONS = {
    ".txt", ".doc", ".docx", ".pdf", ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif",
    ".mp3", ".wav", ".flac", ".mp4", ".mkv", ".avi",
    ".py", ".cpp", ".cs", ".json", ".csv"
}