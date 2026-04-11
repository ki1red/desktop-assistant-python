import os
import webbrowser

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.events.event_models import AssistantAnnouncement
from app.events.notifier import AssistantNotifier
from app.config import ASSISTANT_SETTINGS
from app.session.state import session_state
from app.adaptive.history import register_negative_feedback
from app.providers.router import ProviderRouter


class CommandExecutor:
    def __init__(self):
        self.notifier = AssistantNotifier()
        self.provider_router = ProviderRouter()

    def execute(self, command: ParsedCommand, resolved: ResolvedTarget) -> ExecutionResult:
        if command.intent == "negative_feedback":
            last_resolved = session_state.last_resolved
            if last_resolved and last_resolved.target_path:
                register_negative_feedback(last_resolved.target_path)
                message = f"Понял. Отмечу, что прошлый выбор был ошибочным: {last_resolved.target_name}"
                self.notifier.notify(AssistantAnnouncement(
                    stage="after_execute",
                    text=message,
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

        if command.intent == "reject_deep_search":
            session_state.clear_pending_deep_search()
            self.notifier.say("Глубокий поиск отменён.")
            return ExecutionResult(
                success=True,
                message="Глубокий поиск отменён.",
                intent=command.intent
            )

        if command.intent == "search_web":
            url = self.provider_router.build_default_web_search_url(command.target_text)
            if not url:
                self.notifier.say("Не удалось построить ссылку для веб-поиска.")
                return ExecutionResult(success=False, message="Не удалось построить URL для веб-поиска.", intent=command.intent)

            self.notifier.say(f"Открываю поиск в браузере: {command.target_text}")
            webbrowser.open(url)
            self.notifier.say_random("done")
            return ExecutionResult(success=True, message=f"Открыт веб-поиск: {command.target_text}", intent=command.intent, target_path=url)

        if command.intent == "search_youtube":
            url = self.provider_router.build_default_youtube_url(command.target_text)
            if not url:
                self.notifier.say("Не удалось построить ссылку для YouTube.")
                return ExecutionResult(success=False, message="Не удалось построить URL для YouTube.", intent=command.intent)

            self.notifier.say(f"Открываю поиск на Ютубе: {command.target_text}")
            webbrowser.open(url)
            self.notifier.say_random("done")
            return ExecutionResult(success=True, message=f"Открыт YouTube поиск: {command.target_text}", intent=command.intent, target_path=url)

        if command.intent == "play_music_query":
            url = self.provider_router.build_default_music_url(command.target_text)
            if not url:
                self.notifier.say("Не удалось построить ссылку для музыки.")
                return ExecutionResult(success=False, message="Не удалось построить URL для музыки.", intent=command.intent)

            self.notifier.say(f"Открываю поиск музыки: {command.target_text}")
            webbrowser.open(url)
            self.notifier.say_random("done")
            return ExecutionResult(success=True, message=f"Открыт поиск музыки: {command.target_text}", intent=command.intent, target_path=url)

        if resolved.needs_confirmation:
            self.notifier.notify(AssistantAnnouncement(
                stage="before_execute",
                text=resolved.confirmation_message or "Нужно подтверждение.",
                intent=command.intent,
                target_name=resolved.target_name,
                target_path=resolved.target_path
            ))
            return ExecutionResult(
                success=False,
                message=resolved.confirmation_message or "Нужно подтверждение.",
                intent=command.intent,
                target_path=resolved.target_path
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

        try:
            os.startfile(resolved.target_path)

            success_text = f"Выполнил команду: {resolved.target_name}"
            if ASSISTANT_SETTINGS.get("announce_after_execution", True):
                self.notifier.notify(AssistantAnnouncement(
                    stage="after_execute",
                    text=success_text,
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