from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginCommandSpec, PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult

from app.nlu.parser import CommandParser
from app.executor.executor import CommandExecutor
from app.models import ResolvedTarget


class WebPlugin(AssistantPlugin):
    """
    Встроенный веб-аддон.

    Пока использует старый CommandParser и CommandExecutor.
    """

    plugin_id = "web"
    title = "Веб"
    description = "Поиск в интернете и открытие веб-запросов."
    default_enabled = True

    SUPPORTED_INTENTS = {
        "search_web",
        "search_youtube",
    }

    def __init__(self):
        """
        Создаёт веб-аддон.
        """
        super().__init__()
        self.parser = CommandParser()
        self.executor = CommandExecutor()

    def get_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает команды веб-аддона.
        """
        return [
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="search_web",
                title="Поиск в интернете",
                description="Ищет запрос через выбранный веб-провайдер.",
                examples=[
                    "найди в интернете погоду",
                    "загугли python sqlite",
                    "поищи как установить blender",
                ],
                keywords=[
                    "найди в интернете",
                    "загугли",
                    "поищи",
                    "поиск в интернете",
                    "найди в гугле",
                ],
                intent_hints=["search_web"],
                priority=75,
            ),
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="search_youtube",
                title="Поиск на YouTube",
                description="Ищет запрос на YouTube.",
                examples=[
                    "найди на ютубе музыку",
                    "поищи на youtube туториал blender",
                ],
                keywords=[
                    "ютуб",
                    "youtube",
                    "найди на ютубе",
                    "поищи на ютубе",
                ],
                intent_hints=["search_youtube"],
                priority=80,
            ),
        ]

    def match(self, context: PluginContext) -> PluginMatch:
        """
        Проверяет, относится ли команда к веб-поиску.
        """
        command = self.parser.parse(context.text())

        if command.intent in self.SUPPORTED_INTENTS:
            return PluginMatch(
                plugin_id=self.plugin_id,
                command_id=command.intent,
                score=0.9,
                reason=f"Parser распознал веб-intent={command.intent}",
                metadata={"parsed_command": command},
            )

        return super().match(context)

    def handle(self, context: PluginContext, match: PluginMatch | None = None) -> PluginResult:
        """
        Выполняет веб-команду.
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