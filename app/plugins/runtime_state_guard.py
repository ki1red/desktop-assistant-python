import threading

from app.chat.state import chat_state
from app.dictation.state import dictation_state
from app.logger import get_logger
from app.settings_service import settings_service


logger = get_logger("plugin_runtime_state_guard")


class PluginRuntimeStateGuard:
    """
    Следит за тем, чтобы runtime-состояния режимов не жили отдельно
    от plugins.enabled.

    Если пользователь отключает plugin:
    - chat  -> chat_state выключается;
    - dictation -> dictation_state выключается.

    Это не включает режимы автоматически обратно.
    Повторное включение plugin только возвращает возможность
    снова включить режим вручную или голосовой командой.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._started = False

    def start(self):
        with self._lock:
            if self._started:
                return

            settings_service.subscribe(self._on_settings_changed)
            self._started = True

        self._apply_snapshot(settings_service.get_all())
        logger.info("PluginRuntimeStateGuard запущен.")

    def _on_settings_changed(self, config_snapshot: dict):
        self._apply_snapshot(config_snapshot)

    def _is_plugin_enabled(
        self,
        config_snapshot: dict,
        plugin_id: str,
        default: bool = True,
    ) -> bool:
        plugins_cfg = config_snapshot.get("plugins", {})
        enabled_map = plugins_cfg.get("enabled")

        if isinstance(enabled_map, dict):
            return bool(enabled_map.get(plugin_id, default))

        legacy_enabled = config_snapshot.get("assistant", {}).get("enabled_plugins")
        if isinstance(legacy_enabled, list):
            return plugin_id in {str(item) for item in legacy_enabled}

        return bool(default)

    def _apply_snapshot(self, config_snapshot: dict):
        chat_enabled = self._is_plugin_enabled(config_snapshot, "chat", True)
        dictation_enabled = self._is_plugin_enabled(config_snapshot, "dictation", True)

        if not chat_enabled and chat_state.is_enabled():
            chat_state.disable()
            logger.info("Chat runtime mode автоматически выключен: plugin chat отключён.")

        if not dictation_enabled and dictation_state.is_enabled():
            dictation_state.disable()
            logger.info("Dictation runtime mode автоматически выключен: plugin dictation отключён.")


plugin_runtime_state_guard = PluginRuntimeStateGuard()