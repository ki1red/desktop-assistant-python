from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.plugins.handlers import PluginCommandHandler, PluginExecutionContext
from app.dictation.state import dictation_state
from app.logger import get_logger


logger = get_logger("dictation_plugin_handler")


class DictationPluginHandler(PluginCommandHandler):
    plugin_id = "dictation"

    supported_intents = {
        "enable_dictation",
        "disable_dictation",
    }

    supported_command_ids = {
        "enable_dictation",
        "disable_dictation",
    }

    def execute(
        self,
        command: ParsedCommand,
        resolved: ResolvedTarget,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        """
        Включает или выключает режим диктовки.
        """
        if command.intent == "enable_dictation":
            dictation_state.enable()
            message = "Режим диктовки включён."
            context.notifier.say(message)

            return ExecutionResult(
                success=True,
                message=message,
                intent=command.intent,
            )

        if command.intent == "disable_dictation":
            dictation_state.disable()
            message = "Режим диктовки выключен."
            context.notifier.say(message)

            return ExecutionResult(
                success=True,
                message=message,
                intent=command.intent,
            )

        message = "Команда диктовки не поддерживается."
        logger.warning(
            "DictationPluginHandler | unsupported command | intent=%s command_id=%s",
            command.intent,
            command.command_id,
        )

        context.notifier.say(message)

        return ExecutionResult(
            success=False,
            message=message,
            intent=command.intent,
        )