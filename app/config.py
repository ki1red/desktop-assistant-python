from pathlib import Path

from app.settings_service import settings_service


BASE_DIR = Path(__file__).resolve().parent.parent

_config = settings_service.get_all()

TEMP_DIR = BASE_DIR / _config["paths"]["temp_dir"]
TEMP_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / _config["paths"]["data_dir"]
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = BASE_DIR / _config["paths"]["database_path"]

AUDIO_SAMPLE_RATE = _config["audio"]["sample_rate"]
AUDIO_CHANNELS = _config["audio"]["channels"]
AUDIO_CHUNK_SIZE = _config["audio"]["chunk_size"]
MAX_RECORD_SECONDS = _config["audio"]["max_record_seconds"]
MIN_RECORD_SECONDS = _config["audio"]["min_record_seconds"]
SILENCE_DURATION_STOP_SEC = _config["audio"]["silence_duration_stop_sec"]
SILENCE_THRESHOLD = _config["audio"]["silence_threshold"]

WHISPER_MODEL_SIZE = _config["speech"]["whisper_model_size"]
WHISPER_COMPUTE_TYPE = _config["speech"]["whisper_compute_type"]

INDEX_BATCH_SIZE = _config["search"]["index_batch_size"]
APP_MATCH_THRESHOLD = _config["search"]["app_match_threshold"]
FILE_MATCH_THRESHOLD = _config["search"]["file_match_threshold"]
MAX_CANDIDATES = _config["search"]["max_candidates"]
PRIORITY_CONFIDENT_SCORE = _config["search"]["priority_confident_score"]
USAGE_DIRECT_OPEN_SCORE = _config["search"]["usage_direct_open_score"]

SEARCH_MODE_SETTINGS = _config["search_modes"]
TEMP_CLEANUP_SETTINGS = _config["temp_cleanup"]
ASSISTANT_SETTINGS = _config["assistant"]
PRIORITY_ROOTS_CONFIG = _config["priority_roots"]
BACKGROUND_SETTINGS = _config["background"]
PROVIDER_SETTINGS = _config["providers"]
VOICE_SETTINGS = _config["voice"]


def reload_config():
    global _config
    global AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_CHUNK_SIZE
    global MAX_RECORD_SECONDS, MIN_RECORD_SECONDS, SILENCE_DURATION_STOP_SEC, SILENCE_THRESHOLD
    global WHISPER_MODEL_SIZE, WHISPER_COMPUTE_TYPE
    global INDEX_BATCH_SIZE, APP_MATCH_THRESHOLD, FILE_MATCH_THRESHOLD, MAX_CANDIDATES
    global PRIORITY_CONFIDENT_SCORE, USAGE_DIRECT_OPEN_SCORE
    global SEARCH_MODE_SETTINGS, TEMP_CLEANUP_SETTINGS, ASSISTANT_SETTINGS
    global PRIORITY_ROOTS_CONFIG, BACKGROUND_SETTINGS, PROVIDER_SETTINGS, VOICE_SETTINGS

    _config = settings_service.get_all()

    AUDIO_SAMPLE_RATE = _config["audio"]["sample_rate"]
    AUDIO_CHANNELS = _config["audio"]["channels"]
    AUDIO_CHUNK_SIZE = _config["audio"]["chunk_size"]
    MAX_RECORD_SECONDS = _config["audio"]["max_record_seconds"]
    MIN_RECORD_SECONDS = _config["audio"]["min_record_seconds"]
    SILENCE_DURATION_STOP_SEC = _config["audio"]["silence_duration_stop_sec"]
    SILENCE_THRESHOLD = _config["audio"]["silence_threshold"]

    WHISPER_MODEL_SIZE = _config["speech"]["whisper_model_size"]
    WHISPER_COMPUTE_TYPE = _config["speech"]["whisper_compute_type"]

    INDEX_BATCH_SIZE = _config["search"]["index_batch_size"]
    APP_MATCH_THRESHOLD = _config["search"]["app_match_threshold"]
    FILE_MATCH_THRESHOLD = _config["search"]["file_match_threshold"]
    MAX_CANDIDATES = _config["search"]["max_candidates"]
    PRIORITY_CONFIDENT_SCORE = _config["search"]["priority_confident_score"]
    USAGE_DIRECT_OPEN_SCORE = _config["search"]["usage_direct_open_score"]

    SEARCH_MODE_SETTINGS = _config["search_modes"]
    TEMP_CLEANUP_SETTINGS = _config["temp_cleanup"]
    ASSISTANT_SETTINGS = _config["assistant"]
    PRIORITY_ROOTS_CONFIG = _config["priority_roots"]
    BACKGROUND_SETTINGS = _config["background"]
    PROVIDER_SETTINGS = _config["providers"]
    VOICE_SETTINGS = _config["voice"]