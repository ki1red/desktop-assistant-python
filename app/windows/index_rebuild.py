import threading

from app.logger import get_logger
from app.indexing.index_state import index_state
from app.indexing.indexer import get_index_count


logger = get_logger("index_rebuild")


def rebuild_index_async(notifier=None):
    def worker():
        try:
            index_state.start("Начинаю перестроение индекса...")
            if notifier:
                notifier.say("Начинаю перестроение индекса.")
            logger.info("Запущено перестроение индекса.")

            from build_index import main as build_index_main
            build_index_main()

            count = get_index_count()
            index_state.finish(f"Индексация завершена. Объектов в индексе: {count}")
            logger.info("Перестроение индекса завершено.")
            if notifier:
                notifier.say("Перестроение индекса завершено.")
        except Exception as e:
            logger.exception("Ошибка перестроения индекса: %s", e)
            index_state.finish("Ошибка перестроения индекса.")
            if notifier:
                notifier.say("Ошибка перестроения индекса.")

    threading.Thread(target=worker, daemon=True).start()