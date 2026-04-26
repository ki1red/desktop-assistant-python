import logging
from logging.handlers import RotatingFileHandler

from app.app_paths import LOGS_DIR, LOG_PATH, ensure_app_dirs


LOG_DIR = LOGS_DIR
LOG_FILE = LOG_PATH


def setup_logging():
    ensure_app_dirs()

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
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