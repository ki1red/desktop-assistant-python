from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginCommandSpec, PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult

from app.nlu.parser import CommandParser
from app.executor.executor import CommandExecutor
from app.models import ResolvedTarget


class MusicPlugin(AssistantPlugin):
    """
    Встроенный музыкальный аддон.
    """

    plugin_id = "music"
    title = "Музыка"
    description = "Поиск музыки через выбранный музыкальный сервис."
    default_enabled = True

    SUPPORTED_INTENTS = {
        "play_music_query",
    }

    def __init__(self):
        """
        Создаёт музыкальный аддон.
        """
        super().__init__()
        self.parser = CommandParser()
        self.executor = CommandExecutor()

    def get_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает команды музыкального аддона.
        """
        return [
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="play_music_query",
                title="Найти или включить музыку",
                description="Открывает музыкальный поиск через выбранного провайдера.",
                examples=[
                    "включи музыку queen",
                    "найди песню rammstein sonne",
                    "поставь трек daft punk",
                ],
                keywords=[
                    "включи музыку",
                    "поставь музыку",
                    "найди песню",
                    "включи песню",
                    "поставь трек",
                    "музыка",
                    "песня",
                    "трек",
                ],
                intent_hints=["play_music_query"],
                priority=80,
            ),
        ]

    def match(self, context: PluginContext) -> PluginMatch:
        """
        Проверяет, похожа ли команда на музыкальную.
        """
        command = self.parser.parse(context.text())

        if command.intent in self.SUPPORTED_INTENTS:
            return PluginMatch(
                plugin_id=self.plugin_id,
                command_id=command.intent,
                score=0.9,
                reason=f"Parser распознал музыкальный intent={command.intent}",
                metadata={"parsed_command": command},
            )

        return super().match(context)

    def handle(self, context: PluginContext, match: PluginMatch | None = None) -> PluginResult:
        """
        Выполняет музыкальную команду.
        """
        command = None

        if match and match.metadata.get("parsed_command"):
            command = match.metadata["parsed_command"]
        else:
            command = self.parser.parse(context.text())

        if command.intent not in self.SUPPORTED_INTENTS:
            return PluginResult.not_handled(self.plugin_id)

        execution = self.executor.execute(command, ResolvedTarget(success=False))

        return PluginResult(
            handled=True,
            success=execution.success,
            message=execution.message,
            intent=execution.intent or command.intent,
            plugin_id=self.plugin_id,
            command_id=command.intent,
        )