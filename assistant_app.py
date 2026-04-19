from multiprocessing import freeze_support

from app.logging_config import setup_logging
from app.indexing.db import init_db
from app.speech.recorder import cleanup_old_temp_files
from app.windows.app_runtime import AppRuntime


def main():
    freeze_support()
    setup_logging()
    init_db()
    cleanup_old_temp_files()

    runtime = AppRuntime()
    raise SystemExit(runtime.start())


if __name__ == "__main__":
    main()