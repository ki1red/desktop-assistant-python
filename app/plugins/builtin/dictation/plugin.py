from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginCommandSpec, PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult

from app.nlu.parser import CommandParser
from app.executor.executor import CommandExecutor
from app.models import ResolvedTarget


class DictationPlugin(AssistantPlugin):
    """
    Встроенный аддон диктовки.

    Пока он отвечает за команды включения и выключения диктовки.
    Сам ввод текста пока остаётся в старом pipeline.
    """

    plugin_id = "dictation"
    title = "Диктовка"
    description = "Ввод распознанной речи как текста в активное окно."
    default_enabled = True

    SUPPORTED_INTENTS = {
        "enable_dictation",
        "disable_dictation",
    }

    def __init__(self):
        """
        Создаёт аддон диктовки.
        """
        super().__init__()
        self.parser = CommandParser()
        self.executor = CommandExecutor()

    def get_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает команды диктовки.
        """
        return [
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="enable_dictation",
                title="Включить диктовку",
                description="Переводит ассистента в режим ввода текста.",
                examples=[
                    "включи диктовку",
                    "начать диктовку",
                    "режим диктовки",
                ],
                keywords=[
                    "включи диктовку",
                    "начать диктовку",
                    "режим диктовки",
                ],
                intent_hints=["enable_dictation"],
                priority=85,
            ),
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="disable_dictation",
                title="Выключить диктовку",
                description="Возвращает ассистента из режима диктовки.",
                examples=[
                    "выключи диктовку",
                    "останови диктовку",
                    "заверши диктовку",
                ],
                keywords=[
                    "выключи диктовку",
                    "останови диктовку",
                    "заверши диктовку",
                ],
                intent_hints=["disable_dictation"],
                priority=85,
            ),
        ]

    def match(self, context: PluginContext) -> PluginMatch:
        """
        Проверяет, является ли команда управлением диктовкой.
        """
        command = self.parser.parse(context.text())

        if command.intent in self.SUPPORTED_INTENTS:
            return PluginMatch(
                plugin_id=self.plugin_id,
                command_id=command.intent,
                score=0.95,
                reason=f"Parser распознал dictation intent={command.intent}",
                metadata={"parsed_command": command},
            )

        return super().match(context)

    def handle(self, context: PluginContext, match: PluginMatch | None = None) -> PluginResult:
        """
        Выполняет включение или выключение диктовки.
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