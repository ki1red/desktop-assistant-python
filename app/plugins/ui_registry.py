from dataclasses import dataclass
from typing import Callable

from app.logger import get_logger
from app.plugins.resources import load_builtin_plugin_definitions


logger = get_logger("plugin_ui_registry")


@dataclass(slots=True)
class PluginTabSpec:
    """
    Описание вкладки плагина для MainWindow.

    plugin_id:
        Идентификатор плагина, с которым связана вкладка.

    title:
        Заголовок вкладки в интерфейсе.

    factory:
        Фабрика, создающая QWidget вкладки.

    scrollable:
        Нужно ли автоматически оборачивать вкладку в QScrollArea.
        Для обычных plugin pages почти всегда True.
    """
    plugin_id: str
    title: str
    factory: Callable[[], object]
    scrollable: bool = True
    default_enabled: bool = True


def _builtin_plugin_tab_factories() -> dict[str, tuple[str, Callable[[], object], bool]]:
    """
    Реестр встроенных plugin tabs.

    Пока он пустой намеренно:
    - framework для вкладок уже готов;
    - реальные widget-вкладки плагинов можно добавлять постепенно,
      не ломая текущий UI.

    Когда появится реальный widget плагина, просто добавь сюда запись вида:
        from app.windows.some_plugin_widget import SomePluginWidget
        "chat": ("Общение", SomePluginWidget, True)
    """
    return {}


def get_plugin_tab_specs() -> list[PluginTabSpec]:
    """
    Возвращает список вкладок плагинов в стабильном порядке.

    Порядок берём из plugin resources, чтобы UI был согласован
    с реестром встроенных плагинов.
    """
    definitions = load_builtin_plugin_definitions()
    factory_map = _builtin_plugin_tab_factories()

    specs: list[PluginTabSpec] = []

    for definition in definitions:
        tab_info = factory_map.get(definition.plugin_id)
        if not tab_info:
            continue

        title, factory, scrollable = tab_info

        specs.append(
            PluginTabSpec(
                plugin_id=definition.plugin_id,
                title=title,
                factory=factory,
                scrollable=bool(scrollable),
                default_enabled=bool(definition.default_enabled),
            )
        )

    logger.info(
        "Plugin UI registry loaded: tabs=%s",
        [f"{item.plugin_id}:{item.title}" for item in specs],
    )

    return specs