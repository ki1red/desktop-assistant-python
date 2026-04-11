import threading

from app.logger import get_logger


logger = get_logger("index_rebuild")


def rebuild_index_async(notifier=None):
    def worker():
        try:
            if notifier:
                notifier.say("Начинаю перестроение индекса.")
            logger.info("Запущено перестроение индекса.")

            from build_index import main as build_index_main
            build_index_main()

            logger.info("Перестроение индекса завершено.")
            if notifier:
                notifier.say("Перестроение индекса завершено.")
        except Exception as e:
            logger.exception("Ошибка перестроения индекса: %s", e)
            if notifier:
                notifier.say("Ошибка перестроения индекса.")

    threading.Thread(target=worker, daemon=True).start()