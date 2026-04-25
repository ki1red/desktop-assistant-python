import threading

from app.app_paths import ensure_app_dirs
from app.config_loader import ConfigLoader
from app.indexing.db import init_db
from app.indexing.indexer import rebuild_index, get_index_count
from app.speech.recorder import cleanup_old_temp_files
from app.indexing.index_state import index_state
from app.logger import get_logger
from app.settings_service import settings_service

logger = get_logger("bootstrap")

_index_thread = None
_index_lock = threading.Lock()


def _build_index_worker():
    try:
        logger.info("Запущена первичная индексация.")
        index_state.start("Выполняется первичная индексация файлов...")
        rebuild_index()
        count = get_index_count()
        index_state.finish(f"Индексация завершена. Объектов в индексе: {count}")
        logger.info("Первичная индексация завершена. count=%s", count)
    except Exception as e:
        logger.exception("Ошибка первичной индексации: %s", e)
        index_state.finish(f"Ошибка индексации: {e}")


def ensure_initial_index():
    global _index_thread

    try:
        count = get_index_count()
    except Exception:
        count = 0

    if count > 0:
        index_state.finish(f"Индекс уже готов. Объектов в индексе: {count}")
        logger.info("Индекс уже существует. count=%s", count)
        return

    with _index_lock:
        if _index_thread and _index_thread.is_alive():
            return
        _index_thread = threading.Thread(target=_build_index_worker, daemon=True)
        _index_thread.start()


def bootstrap_app_environment():
    ensure_app_dirs()

    loader = ConfigLoader()
    loader.save(loader.get())

    settings_service.reload()

    init_db()
    cleanup_old_temp_files()
    ensure_initial_index()