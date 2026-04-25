import os
import sys
from pathlib import Path

APP_NAME = "LocalAssistant"


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
    return Path(__file__).resolve().parent.parent


def get_local_app_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_NAME


BUNDLE_ROOT = get_bundle_root()
LOCAL_APP_ROOT = get_local_app_root()

CONFIG_DIR = LOCAL_APP_ROOT / "config"
DATA_DIR = LOCAL_APP_ROOT / "data"
LOGS_DIR = LOCAL_APP_ROOT / "logs"
TEMP_DIR = LOCAL_APP_ROOT / "temp"

USER_CONFIG_PATH = CONFIG_DIR / "settings.json"
DEFAULT_CONFIG_PATH = BUNDLE_ROOT / "config" / "default_settings.json"

DB_PATH = DATA_DIR / "assistant.db"
LOG_PATH = LOGS_DIR / "assistant.log"


def ensure_app_dirs():
    for path in [CONFIG_DIR, DATA_DIR, LOGS_DIR, TEMP_DIR]:
        path.mkdir(parents=True, exist_ok=True)