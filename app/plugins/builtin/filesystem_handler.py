import os

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.events.event_models import AssistantAnnouncement
from app.config import ASSISTANT_SETTINGS
from app.plugins.handlers import PluginCommandHandler, PluginExecutionContext
from app.logger import get_logger


logger = get_logger("filesystem_plugin_handler")


class FilesystemPluginHandler(PluginCommandHandler):
    plugin_id = "filesystem"

    supported_intents = {
        "open_file",
        "open_folder",
        "open_app",
        "generic_open",
        "play_media",
    }

    supported_command_ids = {
        "open_file",
        "open_folder",
        "open_app",
        "open_anything",
    }

    def execute(
        self,
        command: ParsedCommand,
        resolved: ResolvedTarget,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        """
        Открывает локальную цель через os.startfile.

        Если по старой логике пришли candidates без выбранного target_path,
        берём первый кандидат автоматически.
        """
        resolved = self._ensure_first_candidate_selected(resolved)

        if not resolved.success or not resolved.target_path:
            safe_error = context.safe_user_error(resolved.error)

            context.notifier.notify(AssistantAnnouncement(
                stage="error",
                text=safe_error,
                intent=command.intent,
            ))

            return ExecutionResult(
                success=False,
                message=safe_error,
                intent=command.intent,
            )

        try:
            os.startfile(resolved.target_path)

            success_text = f"Выполнил команду: {resolved.target_name}"

            if ASSISTANT_SETTINGS.get("announce_after_execution", True):
                context.notifier.notify(AssistantAnnouncement(
                    stage="after_execute",
                    text=success_text,
                    intent=command.intent,
                    target_name=resolved.target_name,
                    target_path=resolved.target_path,
                ))

            return ExecutionResult(
                success=True,
                message=f"Успешно выполнено: {command.intent} -> {resolved.target_path}",
                intent=command.intent,
                target_path=resolved.target_path,
            )

        except Exception as e:
            logger.exception(
                "Ошибка выполнения filesystem-команды intent=%s target=%s path=%s: %s",
                command.intent,
                resolved.target_name,
                resolved.target_path,
                e,
            )

            context.notifier.notify(AssistantAnnouncement(
                stage="error",
                text="Не удалось выполнить команду.",
                intent=command.intent,
                target_name=resolved.target_name,
                target_path=resolved.target_path,
            ))

            return ExecutionResult(
                success=False,
                message="Не удалось выполнить команду.",
                intent=command.intent,
                target_path=resolved.target_path,
            )

    def _ensure_first_candidate_selected(self, resolved: ResolvedTarget) -> ResolvedTarget:
        """
        Страховка на случай, если старый код вернул candidates,
        но не заполнил target_path.
        """
        if resolved.target_path:
            return resolved

        if not resolved.candidates:
            return resolved

        best = resolved.candidates[0]

        logger.info(
            "FilesystemPluginHandler | target_path пустой, выбран первый candidate | name=%s path=%s",
            getattr(best, "name", None),
            getattr(best, "path", None),
        )

        resolved.success = True
        resolved.target_type = getattr(best, "target_type", None)
        resolved.target_name = getattr(best, "name", None)
        resolved.target_path = getattr(best, "path", None)
        resolved.needs_confirmation = False
        resolved.confirmation_message = None
        resolved.suggests_deep_search = False

        return resolved