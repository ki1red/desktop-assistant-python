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
    except Exception as e:
        logger.exception("Не удалось проверить количество объектов в индексе: %s", e)
        count = 0

    if count > 0:
        index_state.finish(f"Индекс уже готов. Объектов в индексе: {count}")
        logger.info("Индекс уже существует. count=%s", count)
        return

    with _index_lock:
        if _index_thread and _index_thread.is_alive():
            logger.info("Первичная индексация уже выполняется.")
            return

        logger.info("Индекс пустой. Запускаю первичную индексацию в фоне.")
        _index_thread = threading.Thread(target=_build_index_worker, daemon=True)
        _index_thread.start()


def bootstrap_app_environment():
    logger.info("Bootstrap | start")

    logger.info("Bootstrap | ensure app dirs")
    ensure_app_dirs()

    logger.info("Bootstrap | load and save merged config")
    loader = ConfigLoader()

    # Сохраняем результат merge(default_settings + user_settings) обратно в AppData.
    # Это добавляет новые ключи в пользовательский settings.json без потери старых значений.
    loader.save(loader.get())

    logger.info("Bootstrap | reload settings_service")
    settings_service.reload()

    # Важно:
    # app.config содержит глобальные значения TEMP_DIR, DB_PATH, VOICE_SETTINGS и т.д.
    # После settings_service.reload() их тоже нужно обновить.
    try:
        from app.config import reload_config

        reload_config()
        logger.info("Bootstrap | app.config reloaded")
    except Exception as e:
        logger.exception("Bootstrap | не удалось обновить app.config: %s", e)
        raise

    logger.info("Bootstrap | init database")
    init_db()

    logger.info("Bootstrap | cleanup old temp files")
    cleanup_old_temp_files()

    logger.info("Bootstrap | ensure initial index")
    ensure_initial_index()

    logger.info("Bootstrap | done")