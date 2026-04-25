from multiprocessing import freeze_support

from app.bootstrap import bootstrap_app_environment
from app.logging_config import setup_logging
from app.windows.app_runtime import AppRuntime
from app.nlu.resources_loader import nlu_resources
from app.logger import get_logger
from app.app_paths import USER_CONFIG_PATH

startup_logger = get_logger("startup")


def main():
    freeze_support()
    setup_logging()

    startup_logger.info("Запуск приложения.")
    startup_logger.info("Файл пользовательских настроек: %s", USER_CONFIG_PATH)
    startup_logger.info(
        "NLU ресурсы загружены: polite=%s filler=%s verbs=%s dictation=%s extensions=%s",
        len(nlu_resources.polite_words),
        len(nlu_resources.filler_words),
        len(nlu_resources.command_verbs),
        len(nlu_resources.dictation_replacements),
        len(nlu_resources.extension_aliases),
    )

    bootstrap_app_environment()

    from app.settings_service import settings_service
    startup_logger.info("AI config at startup: %s", settings_service.get_section("ai", {}))

    runtime = AppRuntime()
    raise SystemExit(runtime.start())


if __name__ == "__main__":
    main()