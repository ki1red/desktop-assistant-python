from multiprocessing import freeze_support

from app.bootstrap import bootstrap_app_environment
from app.logging_config import setup_logging
from app.windows.app_runtime import AppRuntime
from app.nlu.resources_loader import nlu_resources
from app.logger import get_logger
from app.app_paths import USER_CONFIG_PATH
from app.startup_diagnostics import (
    install_shutdown_logging,
    log_startup_environment,
    log_runtime_paths,
    log_settings_snapshot,
)
from app.settings_service import settings_service


startup_logger = get_logger("startup")


def main():
    freeze_support()

    setup_logging()
    install_shutdown_logging()
    log_startup_environment("after_logging_setup")

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

    startup_logger.info("startup | before bootstrap")
    bootstrap_app_environment()
    startup_logger.info("startup | after bootstrap")

    log_runtime_paths("after_bootstrap")
    log_settings_snapshot(settings_service.get_all(), "after_bootstrap")

    ai_snapshot = settings_service.get_section("ai", {})

    if isinstance(ai_snapshot, dict):
        ai_snapshot = dict(ai_snapshot)

        for secret_key in [
            "api_key",
            "token",
            "access_token",
            "secret",
            "client_secret",
        ]:
            if secret_key in ai_snapshot and ai_snapshot[secret_key]:
                ai_snapshot[secret_key] = "***"

    startup_logger.info("AI config at startup: %s", ai_snapshot)

    startup_logger.info("startup | before AppRuntime")
    runtime = AppRuntime()
    startup_logger.info("startup | after AppRuntime created")

    startup_logger.info("startup | before runtime.start")
    exit_code = runtime.start()
    startup_logger.info("startup | runtime.start returned: %s", exit_code)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()