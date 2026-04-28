import os
import webbrowser

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.events.event_models import AssistantAnnouncement
from app.events.notifier import AssistantNotifier
from app.session.state import session_state
from app.adaptive.history import register_negative_feedback
from app.providers.router import ProviderRouter
from app.custom_commands.admin import CustomCommandsAdmin
from app.plugins.handlers import PluginExecutionContext
from app.plugins.builtin.filesystem_handler import FilesystemPluginHandler
from app.plugins.builtin.web_handler import WebPluginHandler
from app.plugins.builtin.music_handler import MusicPluginHandler
from app.plugins.builtin.dictation_handler import DictationPluginHandler
from app.plugins.builtin.chat_handler import ChatPluginHandler
from app.logger import get_logger


logger = get_logger("executor")


class CommandExecutor:
    """
    Общий executor-диспетчер.

    Он оставляет за собой системные вещи:
    - custom commands;
    - negative feedback;
    - безопасное скрытие технических ошибок.

    Команды плагинов делегируются в plugin handlers.
    """

    LEGACY_CONFIRMATION_INTENTS = {
        "confirm_deep_search",
        "reject_deep_search",
        "select_candidate",
    }

    def __init__(self):
        self.notifier = AssistantNotifier()
        self.provider_router = ProviderRouter()
        self.custom_admin = CustomCommandsAdmin()

        self.plugin_handlers = [
            ChatPluginHandler(),
            DictationPluginHandler(),
            WebPluginHandler(),
            MusicPluginHandler(),
            FilesystemPluginHandler(),
        ]

    def _make_plugin_context(self) -> PluginExecutionContext:
        """
        Создаёт контекст для handlers плагинов.
        """
        return PluginExecutionContext(
            notifier=self.notifier,
            provider_router=self.provider_router,
            safe_user_error=self._safe_user_error,
            target_required_error=self._target_required_error,
        )

    def _find_plugin_handler(self, command: ParsedCommand):
        """
        Находит handler для команды плагина.
        """
        for handler in self.plugin_handlers:
            if handler.can_handle(command):
                return handler

        return None

    def _safe_user_error(self, error_text: str | None) -> str:
        """
        Превращает техническую ошибку в нормальный текст для пользователя.
        """
        raw = (error_text or "").strip()
        lowered = raw.lower()

        technical_markers = [
            "incorrect number of bindings",
            "sqlite",
            "operationalerror",
            "traceback",
            "exception",
            "ошибка поиска:",
        ]

        if any(marker in lowered for marker in technical_markers):
            logger.warning("Техническая ошибка скрыта от пользователя: %s", raw)
            return "Не удалось выполнить поиск. Попробуйте повторить команду."

        if raw:
            return raw

        return "Не удалось определить цель команды."

    def _target_required_error(self, intent: str) -> ExecutionResult:
        """
        Возвращает понятную ошибку, если команда требует цель,
        но target_text пустой.
        """
        message = "Не понял, что именно нужно найти."
        self.notifier.say(message)

        return ExecutionResult(
            success=False,
            message=message,
            intent=intent,
        )

    def _execute_custom_command(self, command: ParsedCommand) -> ExecutionResult:
        """
        Выполняет пользовательскую команду из БД custom_commands.
        """
        row = self.custom_admin.resolve_command(command.normalized_text)

        if not row or not row["is_enabled"]:
            self.notifier.say("Пользовательская команда недоступна.")

            return ExecutionResult(
                success=False,
                message="Пользовательская команда недоступна.",
                intent=command.intent,
            )

        command_type = row["command_type"]
        payload = row["payload"]

        try:
            if command_type == "open_path":
                self.notifier.say(f"Открываю: {payload}")
                os.startfile(payload)
                self.notifier.say_random("done")

                return ExecutionResult(
                    success=True,
                    message=f"Открыт путь: {payload}",
                    intent=command.intent,
                    target_path=payload,
                )

            if command_type == "open_url":
                self.notifier.say("Открываю ссылку.")
                webbrowser.open(payload)
                self.notifier.say_random("done")

                return ExecutionResult(
                    success=True,
                    message=f"Открыта ссылка: {payload}",
                    intent=command.intent,
                    target_path=payload,
                )

            self.notifier.say("Неизвестный тип пользовательской команды.")

            return ExecutionResult(
                success=False,
                message=f"Неизвестный тип пользовательской команды: {command_type}",
                intent=command.intent,
            )

        except Exception as e:
            logger.exception("Ошибка выполнения пользовательской команды: %s", e)
            self.notifier.say("Не удалось выполнить пользовательскую команду.")

            return ExecutionResult(
                success=False,
                message="Не удалось выполнить пользовательскую команду.",
                intent=command.intent,
            )

    def _execute_negative_feedback(self, command: ParsedCommand) -> ExecutionResult:
        """
        Сохраняет негативную обратную связь по последнему действию.
        """
        last_resolved = session_state.last_resolved

        if last_resolved and last_resolved.target_path:
            register_negative_feedback(last_resolved.target_path)

            message = f"Понял. Отмечу, что прошлый выбор был ошибочным: {last_resolved.target_name}"

            self.notifier.notify(AssistantAnnouncement(
                stage="after_execute",
                text=message,
                intent=command.intent,
                target_name=last_resolved.target_name,
                target_path=last_resolved.target_path,
            ))

            return ExecutionResult(
                success=True,
                message="Негативная обратная связь сохранена.",
                intent=command.intent,
                target_path=last_resolved.target_path,
            )

        return ExecutionResult(
            success=False,
            message="Нет последнего действия, которое можно пометить как ошибочное.",
            intent=command.intent,
        )

    def _execute_legacy_confirmation_intent(self, command: ParsedCommand) -> ExecutionResult:
        """
        Старые подтверждения больше не используются.

        Если parser или старый код всё-таки вернул такой intent,
        безопасно отклоняем его без запуска старого сценария.
        """
        session_state.clear_pending_all()

        message = "Подтверждения отключены. Я выбираю лучший вариант автоматически."
        self.notifier.say(message)

        logger.info(
            "Executor | legacy confirmation intent ignored | intent=%s target=%s",
            command.intent,
            command.target_text,
        )

        return ExecutionResult(
            success=False,
            message=message,
            intent=command.intent,
        )

    def execute(self, command: ParsedCommand, resolved: ResolvedTarget) -> ExecutionResult:
        if command.intent == "incomplete_command":
            return self._target_required_error(command.intent)

        if command.intent in self.LEGACY_CONFIRMATION_INTENTS:
            return self._execute_legacy_confirmation_intent(command)

        if command.intent == "negative_feedback":
            return self._execute_negative_feedback(command)

        if command.intent == "custom_command":
            return self._execute_custom_command(command)

        plugin_handler = self._find_plugin_handler(command)
        if plugin_handler:
            logger.info(
                "Executor | delegating to plugin handler | plugin=%s command=%s intent=%s handler=%s",
                command.plugin_id,
                command.command_id,
                command.intent,
                plugin_handler.__class__.__name__,
            )

            return plugin_handler.execute(
                command=command,
                resolved=resolved,
                context=self._make_plugin_context(),
            )

        if resolved.needs_confirmation:
            # Страховка. В новой логике сюда попадать не должны.
            logger.warning(
                "Executor | resolved.needs_confirmation=True, но подтверждения отключены."
            )
            resolved.needs_confirmation = False
            resolved.confirmation_message = None

        if not resolved.success or not resolved.target_path:
            safe_error = self._safe_user_error(resolved.error)

            self.notifier.notify(AssistantAnnouncement(
                stage="error",
                text=safe_error,
                intent=command.intent,
            ))

            return ExecutionResult(
                success=False,
                message=safe_error,
                intent=command.intent,
            )

        # Последний fallback для старых локальных команд,
        # если plugin_id почему-то не был заполнен.
        try:
            os.startfile(resolved.target_path)

            success_text = f"Выполнил команду: {resolved.target_name}"

            self.notifier.notify(AssistantAnnouncement(
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
                "Ошибка fallback-выполнения команды intent=%s target=%s path=%s: %s",
                command.intent,
                resolved.target_name,
                resolved.target_path,
                e,
            )

            self.notifier.notify(AssistantAnnouncement(
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