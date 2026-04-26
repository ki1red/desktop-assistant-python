import logging
import os
from datetime import datetime
from pathlib import Path

from app.app_paths import LOGS_DIR


LOG_DIR = LOGS_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)

_START_STAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
_PROCESS_ID = os.getpid()

# Новый отдельный файл логов на каждый запуск приложения.
LOG_FILE = LOG_DIR / f"assistant_{_START_STAMP}_pid{_PROCESS_ID}.log"


def setup_logging():
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger("startup").info("Логирование настроено. LOG_FILE=%s", LOG_FILE)