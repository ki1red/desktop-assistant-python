from app.settings_service import settings_service
from app.logger import get_logger


logger = get_logger("plugin_settings")


DEFAULT_PLUGIN_ENABLED = {
    "filesystem": True,
    "web": True,
    "music": True,
    "dictation": True,
    "chat": True,
}


def get_plugin_enabled_map() -> dict[str, bool]:
    """
    Возвращает карту включённых плагинов.

    Основной формат:
    {
      "plugins": {
        "enabled": {
          "filesystem": true,
          "web": true,
          ...
        }
      }
    }

    Старый формат assistant.enabled_plugins поддерживается как fallback.
    Обычно до него дело не дойдёт, потому что ConfigLoader теперь сам
    нормализует настройки при загрузке и сохранении.
    """
    cfg = settings_service.get_all()

    plugins_cfg = cfg.get("plugins", {})
    enabled_map = plugins_cfg.get("enabled")

    if isinstance(enabled_map, dict):
        result = dict(DEFAULT_PLUGIN_ENABLED)

        for plugin_id, default_value in DEFAULT_PLUGIN_ENABLED.items():
            result[plugin_id] = bool(enabled_map.get(plugin_id, default_value))

        # Сохраняем неизвестные plugin_id для будущих внешних плагинов.
        for plugin_id, value in enabled_map.items():
            plugin_id = str(plugin_id)
            if plugin_id not in result:
                result[plugin_id] = bool(value)

        return result

    legacy_enabled = cfg.get("assistant", {}).get("enabled_plugins")
    if isinstance(legacy_enabled, list):
        legacy_set = {str(item) for item in legacy_enabled}
        return {
            plugin_id: plugin_id in legacy_set
            for plugin_id in DEFAULT_PLUGIN_ENABLED
        }

    return dict(DEFAULT_PLUGIN_ENABLED)


def is_plugin_enabled(plugin_id: str, default: bool = True) -> bool:
    """
    Проверяет, включён ли конкретный плагин.
    """
    plugin_id = (plugin_id or "").strip()
    if not plugin_id:
        return default

    enabled_map = get_plugin_enabled_map()
    return bool(enabled_map.get(plugin_id, default))


def set_plugin_enabled(plugin_id: str, enabled: bool):
    """
    Сохраняет состояние плагина в plugins.enabled.

    Старый assistant.enabled_plugins также синхронизируется,
    чтобы старый код не конфликтовал с новым.
    """
    plugin_id = (plugin_id or "").strip()
    if not plugin_id:
        return

    def mutate(cfg: dict):
        cfg.setdefault("assistant", {})
        cfg.setdefault("plugins", {})
        cfg["plugins"].setdefault("enabled", {})

        # Гарантируем наличие всех стандартных плагинов.
        current_map = dict(DEFAULT_PLUGIN_ENABLED)

        existing_map = cfg["plugins"].get("enabled", {})
        if isinstance(existing_map, dict):
            for existing_plugin_id, existing_value in existing_map.items():
                current_map[str(existing_plugin_id)] = bool(existing_value)

        current_map[plugin_id] = bool(enabled)

        cfg["plugins"]["enabled"] = current_map

        # Старый совместимый список.
        cfg["assistant"]["enabled_plugins"] = [
            item_id
            for item_id, item_enabled in current_map.items()
            if item_enabled
        ]

    settings_service.update(mutate)

    logger.info(
        "Состояние плагина изменено: plugin_id=%s enabled=%s",
        plugin_id,
        enabled,
    )