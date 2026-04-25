import zipfile
from pathlib import Path
from datetime import datetime

from app.logging_config import LOG_FILE
from app.app_paths import USER_CONFIG_PATH


def build_logs_archive(target_path: str):
    target = Path(target_path)

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if LOG_FILE.exists():
            zf.write(LOG_FILE, arcname="assistant.log")
        if USER_CONFIG_PATH.exists():
            zf.write(USER_CONFIG_PATH, arcname="settings.json")


def default_logs_archive_name() -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"assistant_logs_{ts}.zip"