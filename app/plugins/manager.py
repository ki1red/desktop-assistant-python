from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginCommandSpec
from app.logger import get_logger


logger = get_logger("plugin_manager")


class PluginManager:
    """
    Менеджер аддонов.

    Сейчас он загружает встроенные аддоны.
    Позже сюда можно добавить загрузку внешних аддонов из отдельной папки.
    """

    def __init__(self):
        """
        Создаёт менеджер и загружает доступные аддоны.
        """
        self._plugins: list[AssistantPlugin] = []
        self.reload_plugins()

    def reload_plugins(self):
        """
        Перезагружает список доступных аддонов.
        """
        self._plugins = []

        for plugin_cls in self._builtin_plugin_classes():
            try:
                plugin = plugin_cls()
                self._plugins.append(plugin)
                logger.info("Аддон загружен: %s", plugin.plugin_id)
            except Exception as e:
                logger.exception("Не удалось загрузить аддон %s: %s", plugin_cls, e)

    def _builtin_plugin_classes(self):
        """
        Возвращает классы встроенных аддонов.
        """
        from app.plugins.builtin.filesystem.plugin import FileSystemPlugin
        from app.plugins.builtin.web.plugin import WebPlugin
        from app.plugins.builtin.music.plugin import MusicPlugin
        from app.plugins.builtin.dictation.plugin import DictationPlugin
        from app.plugins.builtin.chat.plugin import ChatPlugin

        return [
            FileSystemPlugin,
            WebPlugin,
            MusicPlugin,
            DictationPlugin,
            ChatPlugin,
        ]

    def get_all_plugins(self) -> list[AssistantPlugin]:
        """
        Возвращает все загруженные аддоны.
        """
        return list(self._plugins)

    def get_enabled_plugins(self) -> list[AssistantPlugin]:
        """
        Возвращает только включённые аддоны.
        """
        return [plugin for plugin in self._plugins if plugin.is_enabled()]

    def get_all_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает список команд всех включённых аддонов.
        """
        specs: list[PluginCommandSpec] = []

        for plugin in self.get_enabled_plugins():
            try:
                specs.extend(plugin.get_command_specs())
            except Exception as e:
                logger.exception(
                    "Не удалось получить команды аддона %s: %s",
                    plugin.plugin_id,
                    e,
                )

        return specs

    def get_plugin_by_id(self, plugin_id: str) -> AssistantPlugin | None:
        """
        Ищет аддон по его plugin_id.
        """
        for plugin in self._plugins:
            if plugin.plugin_id == plugin_id:
                return plugin

        return None