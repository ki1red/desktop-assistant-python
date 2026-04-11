from app.logging_config import setup_logging
from app.indexing.db import init_db
from app.speech.recorder import cleanup_old_temp_files
from app.windows.background_service import BackgroundAssistantService

import time


def main():
    setup_logging()
    init_db()
    cleanup_old_temp_files()

    service = BackgroundAssistantService()
    service.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()