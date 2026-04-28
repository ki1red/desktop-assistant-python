from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.plugins.handlers import PluginCommandHandler, PluginExecutionContext
from app.chat.state import chat_state
from app.logger import get_logger


logger = get_logger("chat_plugin_handler")


class ChatPluginHandler(PluginCommandHandler):
    plugin_id = "chat"

    supported_intents = {
        "enable_chat_mode",
        "disable_chat_mode",
    }

    supported_command_ids = {
        "enable_chat_mode",
        "disable_chat_mode",
    }

    def execute(
        self,
        command: ParsedCommand,
        resolved: ResolvedTarget,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        """
        Включает или выключает режим общения с ИИ.
        """
        if command.intent == "enable_chat_mode":
            chat_state.enable()
            message = "Режим общения включён."
            context.notifier.say(message)

            return ExecutionResult(
                success=True,
                message=message,
                intent=command.intent,
            )

        if command.intent == "disable_chat_mode":
            chat_state.disable()
            message = "Режим общения выключен."
            context.notifier.say(message)

            return ExecutionResult(
                success=True,
                message=message,
                intent=command.intent,
            )

        message = "Команда режима общения не поддерживается."
        logger.warning(
            "ChatPluginHandler | unsupported command | intent=%s command_id=%s",
            command.intent,
            command.command_id,
        )

        context.notifier.say(message)

        return ExecutionResult(
            success=False,
            message=message,
            intent=command.intent,
        )