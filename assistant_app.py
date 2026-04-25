from multiprocessing import freeze_support

from app.bootstrap import bootstrap_app_environment
from app.logging_config import setup_logging
from app.windows.app_runtime import AppRuntime


def main():
    freeze_support()
    setup_logging()
    bootstrap_app_environment()

    runtime = AppRuntime()
    raise SystemExit(runtime.start())


if __name__ == "__main__":
    main()