import webbrowser

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.plugins.handlers import PluginCommandHandler, PluginExecutionContext
from app.logger import get_logger


logger = get_logger("web_plugin_handler")


class WebPluginHandler(PluginCommandHandler):
    plugin_id = "web"

    supported_intents = {
        "search_web",
        "search_youtube",
    }

    supported_command_ids = {
        "search_web",
        "search_youtube",
    }

    def execute(
        self,
        command: ParsedCommand,
        resolved: ResolvedTarget,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        """
        Выполняет веб-команды: поиск в браузере и поиск на YouTube.
        """
        target_text = (command.target_text or "").strip()

        if not target_text:
            return context.target_required_error(command.intent)

        if command.intent == "search_web":
            return self._execute_web_search(command, target_text, context)

        if command.intent == "search_youtube":
            return self._execute_youtube_search(command, target_text, context)

        message = "Веб-команда не поддерживается."
        logger.warning(
            "WebPluginHandler | unsupported command | intent=%s command_id=%s",
            command.intent,
            command.command_id,
        )

        context.notifier.say(message)

        return ExecutionResult(
            success=False,
            message=message,
            intent=command.intent,
        )

    def _execute_web_search(
        self,
        command: ParsedCommand,
        target_text: str,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        url = context.provider_router.build_default_web_search_url(target_text)

        if not url:
            message = "Не удалось построить ссылку для веб-поиска."
            context.notifier.say(message)

            return ExecutionResult(
                success=False,
                message=message,
                intent=command.intent,
            )

        context.notifier.say(f"Открываю поиск в браузере: {target_text}")
        webbrowser.open(url)
        context.notifier.say_random("done")

        return ExecutionResult(
            success=True,
            message=f"Открыт веб-поиск: {target_text}",
            intent=command.intent,
            target_path=url,
        )

    def _execute_youtube_search(
        self,
        command: ParsedCommand,
        target_text: str,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        url = context.provider_router.build_default_youtube_url(target_text)

        if not url:
            message = "Не удалось построить ссылку для YouTube."
            context.notifier.say(message)

            return ExecutionResult(
                success=False,
                message=message,
                intent=command.intent,
            )

        context.notifier.say(f"Открываю поиск на Ютубе: {target_text}")
        webbrowser.open(url)
        context.notifier.say_random("done")

        return ExecutionResult(
            success=True,
            message=f"Открыт YouTube поиск: {target_text}",
            intent=command.intent,
            target_path=url,
        )