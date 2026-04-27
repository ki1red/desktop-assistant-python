from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult
from app.logger import get_logger


logger = get_logger("plugin_router")


class PluginCommandRouter:
    """
    Роутер команд между подключёнными аддонами.

    Он получает текст после STT и выбирает аддон,
    который лучше всего подходит для выполнения команды.
    """

    def __init__(self, min_score: float = 0.45):
        """
        Создаёт роутер с минимальным порогом совпадения.
        """
        self.min_score = min_score

    def find_best_match(
        self,
        context: PluginContext,
        plugins: list[AssistantPlugin],
    ) -> tuple[AssistantPlugin | None, PluginMatch | None]:
        """
        Ищет лучший аддон для текущей команды.
        """
        best_plugin = None
        best_match = None

        for plugin in plugins:
            if not plugin.is_enabled():
                continue

            try:
                match = plugin.match(context)
            except Exception as e:
                logger.exception(
                    "Ошибка match() у аддона %s: %s",
                    plugin.plugin_id,
                    e,
                )
                continue

            logger.info(
                "Plugin match | plugin=%s command=%s score=%.3f reason=%s",
                plugin.plugin_id,
                match.command_id,
                match.score,
                match.reason,
            )

            if best_match is None or match.score > best_match.score:
                best_plugin = plugin
                best_match = match

        if best_match is None or best_match.score < self.min_score:
            return None, best_match

        return best_plugin, best_match

    def route(
        self,
        context: PluginContext,
        plugins: list[AssistantPlugin],
    ) -> PluginResult:
        """
        Находит подходящий аддон и запускает выполнение команды.
        """
        plugin, match = self.find_best_match(context, plugins)

        if plugin is None:
            return PluginResult.fail(
                message="Не удалось определить, какой аддон должен выполнить команду.",
                plugin_id="router",
                command_id="unknown",
                intent="plugin_route_failed",
            )

        try:
            return plugin.handle(context, match)
        except Exception as e:
            logger.exception(
                "Ошибка выполнения команды аддоном %s: %s",
                plugin.plugin_id,
                e,
            )
            return PluginResult.fail(
                message=f"Ошибка выполнения команды аддоном «{plugin.title}».",
                plugin_id=plugin.plugin_id,
                command_id=match.command_id if match else "",
                intent="plugin_execution_failed",
            )