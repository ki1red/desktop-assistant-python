from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "assistant_index.db"

AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

WHISPER_MODEL_SIZE = "small"
WHISPER_COMPUTE_TYPE = "int8"

INDEX_BATCH_SIZE = 500

APP_MATCH_THRESHOLD = 78
FILE_MATCH_THRESHOLD = 78