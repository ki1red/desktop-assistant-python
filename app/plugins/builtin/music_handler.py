import webbrowser

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.plugins.handlers import PluginCommandHandler, PluginExecutionContext
from app.logger import get_logger


logger = get_logger("music_plugin_handler")


class MusicPluginHandler(PluginCommandHandler):
    plugin_id = "music"

    supported_intents = {
        "play_music_query",
    }

    supported_command_ids = {
        "play_music_query",
    }

    def execute(
        self,
        command: ParsedCommand,
        resolved: ResolvedTarget,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        """
        Выполняет поиск музыки через выбранного провайдера.
        """
        target_text = (command.target_text or "").strip()

        if not target_text:
            return context.target_required_error(command.intent)

        url = context.provider_router.build_default_music_url(target_text)

        if not url:
            message = "Не удалось построить ссылку для музыки."
            context.notifier.say(message)

            return ExecutionResult(
                success=False,
                message=message,
                intent=command.intent,
            )

        context.notifier.say(f"Открываю поиск музыки: {target_text}")
        webbrowser.open(url)
        context.notifier.say_random("done")

        return ExecutionResult(
            success=True,
            message=f"Открыт поиск музыки: {target_text}",
            intent=command.intent,
            target_path=url,
        )