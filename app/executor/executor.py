import os

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.events.event_models import AssistantAnnouncement
from app.events.notifier import AssistantNotifier
from app.config import ASSISTANT_SETTINGS
from app.session.state import session_state
from app.adaptive.history import register_negative_feedback


class CommandExecutor:
    def __init__(self):
        self.notifier = AssistantNotifier()

    def execute(self, command: ParsedCommand, resolved: ResolvedTarget) -> ExecutionResult:
        if command.intent == "negative_feedback":
            last_resolved = session_state.last_resolved
            if last_resolved and last_resolved.target_path:
                register_negative_feedback(last_resolved.target_path)
                self.notifier.notify(AssistantAnnouncement(
                    stage="after_execute",
                    text=f"Понял. Отмечу, что прошлый выбор был ошибочным: {last_resolved.target_name}",
                    intent=command.intent,
                    target_name=last_resolved.target_name,
                    target_path=last_resolved.target_path
                ))
                return ExecutionResult(
                    success=True,
                    message="Негативная обратная связь сохранена.",
                    intent=command.intent,
                    target_path=last_resolved.target_path
                )

            return ExecutionResult(
                success=False,
                message="Нет последнего действия, которое можно пометить как ошибочное.",
                intent=command.intent
            )

        if not resolved.success or not resolved.target_path:
            self.notifier.notify(AssistantAnnouncement(
                stage="error",
                text=resolved.error or "Не удалось определить цель команды.",
                intent=command.intent
            ))
            return ExecutionResult(
                success=False,
                message=resolved.error or "Цель не была найдена.",
                intent=command.intent
            )

        if ASSISTANT_SETTINGS.get("announce_before_execution", True):
            self.notifier.notify(AssistantAnnouncement(
                stage="before_execute",
                text=f"Сейчас выполню команду: {command.intent}. Цель: {resolved.target_name}",
                intent=command.intent,
                target_name=resolved.target_name,
                target_path=resolved.target_path
            ))

        try:
            os.startfile(resolved.target_path)

            if ASSISTANT_SETTINGS.get("announce_after_execution", True):
                self.notifier.notify(AssistantAnnouncement(
                    stage="after_execute",
                    text=f"Команда выполнена успешно: {resolved.target_name}",
                    intent=command.intent,
                    target_name=resolved.target_name,
                    target_path=resolved.target_path
                ))

            return ExecutionResult(
                success=True,
                message=f"Успешно выполнено: {command.intent} -> {resolved.target_path}",
                intent=command.intent,
                target_path=resolved.target_path
            )
        except Exception as e:
            self.notifier.notify(AssistantAnnouncement(
                stage="error",
                text=f"Не удалось выполнить команду: {e}",
                intent=command.intent,
                target_name=resolved.target_name,
                target_path=resolved.target_path
            ))

            return ExecutionResult(
                success=False,
                message=f"Ошибка выполнения: {e}",
                intent=command.intent,
                target_path=resolved.target_path
            )