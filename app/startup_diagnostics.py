import atexit
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any


logger = logging.getLogger("startup_diag")

_shutdown_logging_installed = False


def _safe_str(value: Any) -> str:
    try:
        if isinstance(value, Path):
            return str(value)
        return str(value)
    except Exception:
        return "<unprintable>"


def _path_info(path_value: Any) -> dict:
    try:
        path = Path(path_value)
        return {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }
    except Exception as e:
        return {
            "path": _safe_str(path_value),
            "error": str(e),
        }


def _log_path(label: str, path_value: Any):
    info = _path_info(path_value)

    if "error" in info:
        logger.warning(
            "PATH | %s | path=%s | error=%s",
            label,
            info.get("path"),
            info.get("error"),
        )
        return

    logger.info(
        "PATH | %s | path=%s | exists=%s | is_file=%s | is_dir=%s",
        label,
        info["path"],
        info["exists"],
        info["is_file"],
        info["is_dir"],
    )


def _check_directory_writable(label: str, path_value: Any):
    try:
        path = Path(path_value)

        if not path.exists():
            logger.warning("WRITE_TEST | %s | skipped | directory does not exist: %s", label, path)
            return

        if not path.is_dir():
            logger.warning("WRITE_TEST | %s | skipped | not a directory: %s", label, path)
            return

        test_file = path / ".startup_write_test.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)

        logger.info("WRITE_TEST | %s | ok | %s", label, path)

    except Exception as e:
        logger.warning("WRITE_TEST | %s | failed | %s | %s", label, path_value, e)


def install_shutdown_logging():
    global _shutdown_logging_installed

    if _shutdown_logging_installed:
        return

    _shutdown_logging_installed = True

    def _on_exit():
        try:
            logger.info("SHUTDOWN | process exiting")
        except Exception:
            pass

    atexit.register(_on_exit)
    logger.info("SHUTDOWN | atexit hook installed")


def log_startup_environment(stage: str = "startup"):
    try:
        logger.info("DIAG | %s | environment_start", stage)

        logger.info("ENV | python_version=%s", sys.version.replace("\n", " "))
        logger.info("ENV | executable=%s", sys.executable)
        logger.info("ENV | platform=%s", platform.platform())
        logger.info("ENV | machine=%s", platform.machine())
        logger.info("ENV | processor=%s", platform.processor())
        logger.info("ENV | cwd=%s", os.getcwd())
        logger.info("ENV | argv=%s", sys.argv)
        logger.info("ENV | frozen=%s", bool(getattr(sys, "frozen", False)))

        project_root = Path(__file__).resolve().parent.parent
        _log_path("project_root", project_root)

        env_keys = [
            "LOCALAPPDATA",
            "APPDATA",
            "USERPROFILE",
            "TEMP",
            "TMP",
            "PATH",
        ]

        for key in env_keys:
            value = os.environ.get(key, "")
            if key == "PATH":
                logger.info("ENV | %s entries=%s", key, len(value.split(os.pathsep)) if value else 0)
            else:
                logger.info("ENV | %s=%s", key, value)

        logger.info("DIAG | %s | environment_done", stage)

    except Exception as e:
        logger.exception("DIAG | %s | environment_failed: %s", stage, e)


def log_runtime_paths(stage: str = "runtime_paths"):
    try:
        logger.info("DIAG | %s | paths_start", stage)

        local_appdata = os.environ.get("LOCALAPPDATA", "")
        fallback_app_dir = Path(local_appdata) / "LocalAssistant" if local_appdata else None

        if fallback_app_dir:
            _log_path("fallback_app_dir", fallback_app_dir)
            _log_path("fallback_config_dir", fallback_app_dir / "config")
            _log_path("fallback_settings_path", fallback_app_dir / "config" / "settings.json")
            _log_path("fallback_data_dir", fallback_app_dir / "data")
            _log_path("fallback_temp_dir", fallback_app_dir / "temp")
            _log_path("fallback_logs_dir", fallback_app_dir / "logs")
            _log_path("fallback_db_path", fallback_app_dir / "data" / "assistant.db")

        try:
            import app.app_paths as app_paths

            path_constant_names = [
                "APP_NAME",
                "BUNDLE_ROOT",
                "LOCAL_APP_ROOT",
                "CONFIG_DIR",
                "DATA_DIR",
                "LOGS_DIR",
                "TEMP_DIR",
                "USER_CONFIG_PATH",
                "DEFAULT_CONFIG_PATH",
                "DB_PATH",
                "LOG_PATH",
            ]

            for name in path_constant_names:
                if hasattr(app_paths, name):
                    value = getattr(app_paths, name)

                    if name == "APP_NAME":
                        logger.info("APP_PATHS | %s=%s", name, value)
                    else:
                        _log_path(f"app_paths.{name}", value)

        except ModuleNotFoundError:
            logger.warning("DIAG | %s | app.app_paths module not found", stage)
        except Exception as e:
            logger.exception("DIAG | %s | app.app_paths import/check failed: %s", stage, e)

        try:
            import app.logging_config as logging_config

            if hasattr(logging_config, "LOG_DIR"):
                _log_path("logging_config.LOG_DIR", logging_config.LOG_DIR)

            if hasattr(logging_config, "LOG_FILE"):
                _log_path("logging_config.LOG_FILE", logging_config.LOG_FILE)

        except Exception as e:
            logger.exception("DIAG | %s | logging_config check failed: %s", stage, e)

        try:
            import app.config as runtime_config

            runtime_names = [
                "TEMP_DIR",
                "DATA_DIR",
                "DB_PATH",
            ]

            for name in runtime_names:
                if hasattr(runtime_config, name):
                    _log_path(f"config.{name}", getattr(runtime_config, name))

        except Exception as e:
            logger.exception("DIAG | %s | app.config check failed: %s", stage, e)

        if fallback_app_dir:
            _check_directory_writable("fallback_app_dir", fallback_app_dir)
            _check_directory_writable("fallback_config_dir", fallback_app_dir / "config")
            _check_directory_writable("fallback_data_dir", fallback_app_dir / "data")
            _check_directory_writable("fallback_temp_dir", fallback_app_dir / "temp")
            _check_directory_writable("fallback_logs_dir", fallback_app_dir / "logs")

        logger.info("DIAG | %s | paths_done", stage)

    except Exception as e:
        logger.exception("DIAG | %s | paths_failed: %s", stage, e)


def log_settings_snapshot(settings: dict, stage: str = "settings"):
    try:
        logger.info("DIAG | %s | settings_start", stage)

        if not isinstance(settings, dict):
            logger.warning("SETTINGS | snapshot is not dict: %s", type(settings))
            return

        logger.info("SETTINGS | top_level_keys=%s", sorted(settings.keys()))

        paths = settings.get("paths", {})
        audio = settings.get("audio", {})
        speech = settings.get("speech", {})
        background = settings.get("background", {})
        ai = settings.get("ai", {})
        search = settings.get("search", {})
        temp_cleanup = settings.get("temp_cleanup", {})
        priority_roots = settings.get("priority_roots", {})

        logger.info("SETTINGS | paths=%s", paths)

        logger.info(
            "SETTINGS | audio | sample_rate=%s channels=%s device_index=%s input_gain=%s max_record=%s silence_stop=%s silence_threshold=%s",
            audio.get("sample_rate"),
            audio.get("channels"),
            audio.get("input_device_index"),
            audio.get("input_gain"),
            audio.get("max_record_seconds"),
            audio.get("silence_duration_stop_sec"),
            audio.get("silence_threshold"),
        )

        logger.info(
            "SETTINGS | speech | model=%s compute_type=%s language=%s fallback=%s",
            speech.get("whisper_model_size"),
            speech.get("whisper_compute_type"),
            speech.get("command_language"),
            speech.get("fallback_to_auto_language"),
        )

        logger.info(
            "SETTINGS | background | enabled=%s hotkey=%s double_press_cancels=%s",
            background.get("enabled"),
            background.get("hotkey"),
            background.get("double_press_cancels"),
        )

        logger.info(
            "SETTINGS | ai | enabled=%s provider=%s apply_to_all_commands=%s refine_dictation=%s timeout=%s speak=%s host=%s main_model=%s chat_model=%s",
            ai.get("enabled"),
            ai.get("provider"),
            ai.get("apply_to_all_commands"),
            ai.get("refine_dictation"),
            ai.get("command_refine_timeout_sec"),
            ai.get("speak_responses"),
            ai.get("ollama_host"),
            ai.get("ollama_model"),
            ai.get("chat_ollama_model"),
        )

        logger.info(
            "SETTINGS | search | app_threshold=%s file_threshold=%s max_candidates=%s index_batch_size=%s",
            search.get("app_match_threshold"),
            search.get("file_match_threshold"),
            search.get("max_candidates"),
            search.get("index_batch_size"),
        )

        logger.info(
            "SETTINGS | temp_cleanup | delete_record=%s delete_old=%s max_age_hours=%s",
            temp_cleanup.get("delete_record_after_transcribe"),
            temp_cleanup.get("delete_old_temp_on_startup"),
            temp_cleanup.get("max_temp_age_hours"),
        )

        extra_paths = priority_roots.get("extra_paths", [])
        logger.info(
            "SETTINGS | priority_roots | cwd=%s desktop=%s documents=%s downloads=%s recent=%s start_menu_user=%s start_menu_common=%s extra_paths_count=%s",
            priority_roots.get("cwd"),
            priority_roots.get("desktop"),
            priority_roots.get("documents"),
            priority_roots.get("downloads"),
            priority_roots.get("recent"),
            priority_roots.get("start_menu_user"),
            priority_roots.get("start_menu_common"),
            len(extra_paths) if isinstance(extra_paths, list) else "not_list",
        )

        logger.info("DIAG | %s | settings_done", stage)

    except Exception as e:
        logger.exception("DIAG | %s | settings_failed: %s", stage, e)