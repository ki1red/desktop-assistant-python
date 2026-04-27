from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginCommandSpec, PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult

from app.nlu.parser import CommandParser
from app.executor.executor import CommandExecutor
from app.models import ResolvedTarget


class ChatPlugin(AssistantPlugin):
    """
    Встроенный аддон общения.

    Пока отвечает за включение и выключение режима общения.
    Сам диалог с ИИ пока остаётся в старом pipeline.
    """

    plugin_id = "chat"
    title = "Общение"
    description = "Режим разговора с ИИ."
    default_enabled = True

    SUPPORTED_INTENTS = {
        "enable_chat_mode",
        "disable_chat_mode",
    }

    def __init__(self):
        """
        Создаёт аддон общения.
        """
        super().__init__()
        self.parser = CommandParser()
        self.executor = CommandExecutor()

    def get_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает команды режима общения.
        """
        return [
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="enable_chat_mode",
                title="Включить режим общения",
                description="Переводит ассистента в режим диалога с ИИ.",
                examples=[
                    "включи режим общения",
                    "давай поговорим",
                    "ассистент режим общения",
                ],
                keywords=[
                    "включи режим общения",
                    "давай поговорим",
                    "режим общения",
                ],
                intent_hints=["enable_chat_mode"],
                priority=85,
            ),
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="disable_chat_mode",
                title="Выключить режим общения",
                description="Выключает режим диалога с ИИ.",
                examples=[
                    "выключи режим общения",
                    "хватит общаться",
                    "заверши общение",
                ],
                keywords=[
                    "выключи режим общения",
                    "хватит общаться",
                    "заверши общение",
                    "режим общения выключить",
                ],
                intent_hints=["disable_chat_mode"],
                priority=85,
            ),
        ]

    def match(self, context: PluginContext) -> PluginMatch:
        """
        Проверяет, является ли команда управлением режимом общения.
        """
        command = self.parser.parse(context.text())

        if command.intent in self.SUPPORTED_INTENTS:
            return PluginMatch(
                plugin_id=self.plugin_id,
                command_id=command.intent,
                score=0.95,
                reason=f"Parser распознал chat intent={command.intent}",
                metadata={"parsed_command": command},
            )

        return super().match(context)

    def handle(self, context: PluginContext, match: PluginMatch | None = None) -> PluginResult:
        """
        Выполняет включение или выключение режима общения.
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