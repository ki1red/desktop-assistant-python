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

    Здесь регистрируются реальные вкладки плагинов.
    Добавляем их постепенно, не ломая существующий UI.
    """
    from app.windows.chat_plugin_widget import ChatPluginWidget
    from app.windows.dictation_plugin_widget import DictationPluginWidget
    from app.windows.music_plugin_widget import MusicPluginWidget
    from app.windows.web_plugin_widget import WebPluginWidget
    from app.windows.filesystem_plugin_widget import FilesystemPluginWidget

    return {
        "chat": ("Общение", ChatPluginWidget, True),
        "dictation": ("Диктовка", DictationPluginWidget, True),
        "music": ("Музыка", MusicPluginWidget, True),
        "web": ("Веб", WebPluginWidget, True),
        "filesystem": ("Файловая система", FilesystemPluginWidget, True),
    }


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