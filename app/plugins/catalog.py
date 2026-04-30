from dataclasses import dataclass

from app.plugins.defaults import DEFAULT_PLUGIN_ENABLED
from app.plugins.resources import load_builtin_plugin_definitions
from app.plugins.settings import get_plugin_enabled_map


@dataclass(slots=True)
class PluginCatalogItem:
    """
    UI-описание плагина.

    Это отдельный лёгкий слой метаданных для интерфейса:
    - что показать пользователю;
    - в каком порядке;
    - встроенный это плагин или внешний/неизвестный.
    """

    plugin_id: str
    title: str
    description: str
    default_enabled: bool = True
    is_builtin: bool = True


def get_plugin_catalog_items() -> list[PluginCatalogItem]:
    """
    Возвращает список плагинов для UI и настроек.

    Источник правды для встроенных плагинов:
    app/plugins/builtin/commands.json

    Если в settings.json уже есть неизвестные plugin_id
    (например, задел под внешние плагины),
    они тоже не теряются и показываются в интерфейсе.
    """
    definitions = load_builtin_plugin_definitions()
    enabled_map = get_plugin_enabled_map()

    items: list[PluginCatalogItem] = []
    known_ids: set[str] = set()

    for definition in definitions:
        known_ids.add(definition.plugin_id)
        items.append(
            PluginCatalogItem(
                plugin_id=definition.plugin_id,
                title=definition.title or definition.plugin_id,
                description=definition.description or "",
                default_enabled=bool(
                    DEFAULT_PLUGIN_ENABLED.get(
                        definition.plugin_id,
                        definition.default_enabled,
                    )
                ),
                is_builtin=True,
            )
        )

    # Неизвестные plugin_id из настроек не удаляем и не скрываем.
    # Это пригодится для будущих внешних плагинов и мягкой миграции.
    for plugin_id, enabled in enabled_map.items():
        plugin_id = str(plugin_id).strip()
        if not plugin_id or plugin_id in known_ids:
            continue

        items.append(
            PluginCatalogItem(
                plugin_id=plugin_id,
                title=f"Плагин: {plugin_id}",
                description="Дополнительный плагин. Описание для него пока не задано.",
                default_enabled=bool(enabled),
                is_builtin=False,
            )
        )

    return items