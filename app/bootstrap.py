import threading

from app.app_paths import ensure_app_dirs
from app.config_loader import ConfigLoader
from app.indexing.db import init_db, get_index_metadata, set_index_metadata_many
from app.indexing.indexer import rebuild_index, get_index_count
from app.speech.recorder import cleanup_old_temp_files
from app.indexing.index_state import index_state
from app.logger import get_logger
from app.settings_service import settings_service


logger = get_logger("bootstrap")

_index_thread = None
_index_lock = threading.Lock()


def _build_index_worker(reason: str = "startup"):
    try:
        logger.info("Запущена индексация. reason=%s", reason)
        index_state.start("Выполняется индексация файлов...")

        rebuild_index()

        count = get_index_count()
        index_state.finish(
            f"Индексация завершена. Объектов в индексе: {count}",
            indexed_count=count,
        )

        logger.info("Индексация завершена. reason=%s count=%s", reason, count)

    except Exception as e:
        logger.exception("Ошибка индексации. reason=%s error=%s", reason, e)
        index_state.fail(f"Ошибка индексации: {e}", error=str(e))


def _index_is_complete(count: int, status: str, last_finished_at: str) -> bool:
    if count <= 0:
        return False

    if status == "":
        return True

    if status == "ready":
        return True

    return False


def ensure_initial_index(reason: str = "startup", force: bool = False):
    """
    Проверяет наличие индекса и при необходимости запускает индексацию в фоне.

    Если прошлый запуск был закрыт во время индексации, metadata останется
    в состоянии building/failed. В таком случае индекс запускается заново.
    """
    global _index_thread

    try:
        init_db()
    except Exception as e:
        logger.exception("Не удалось инициализировать БД перед проверкой индекса: %s", e)

    try:
        count = get_index_count()
    except Exception as e:
        logger.exception("Не удалось проверить количество объектов в индексе: %s", e)
        count = 0

    status = get_index_metadata("index_status", "")
    last_finished_at = get_index_metadata("last_finished_at", "")

    logger.info(
        "Проверка индекса | reason=%s force=%s status=%r last_finished_at=%r count=%s",
        reason,
        force,
        status,
        last_finished_at,
        count,
    )

    if not force and _index_is_complete(count, status, last_finished_at):
        if not status:
            set_index_metadata_many({
                "index_status": "ready",
                "indexed_count": count,
                "last_error": "",
            })

        index_state.finish(
            f"Индекс уже готов. Объектов в индексе: {count}",
            indexed_count=count,
        )
        logger.info("Индекс уже существует. count=%s status=%r", count, status)
        return

    if status == "building":
        logger.warning(
            "Обнаружена незавершённая индексация прошлого запуска. Запускаю индексацию заново. count=%s",
            count,
        )

    elif status == "failed":
        logger.warning(
            "Обнаружен индекс со статусом failed. Запускаю индексацию заново. count=%s",
            count,
        )

    elif count <= 0:
        logger.warning("Индекс отсутствует или пустой. Запускаю индексацию.")
        index_state.mark_missing("Индекс отсутствует. Запускаю восстановление индекса.")

    elif force:
        logger.info("Запрошена принудительная переиндексация. count=%s status=%r", count, status)

    else:
        logger.warning(
            "Состояние индекса неопределённое. Запускаю переиндексацию. count=%s status=%r",
            count,
            status,
        )

    with _index_lock:
        if _index_thread and _index_thread.is_alive():
            logger.info("Индексация уже выполняется. Новый запуск не требуется.")
            return

        logger.info("Запускаю индексацию в фоне. reason=%s force=%s", reason, force)

        _index_thread = threading.Thread(
            target=_build_index_worker,
            args=(reason,),
            daemon=True,
        )
        _index_thread.start()


def bootstrap_app_environment():
    logger.info("Bootstrap | start")

    logger.info("Bootstrap | ensure app dirs")
    ensure_app_dirs()

    logger.info("Bootstrap | load and save merged config")
    loader = ConfigLoader()

    loader.save(loader.get())

    logger.info("Bootstrap | reload settings_service")
    settings_service.reload()

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
    ensure_initial_index(reason="startup")

    logger.info("Bootstrap | done")