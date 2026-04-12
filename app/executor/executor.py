import os
import webbrowser

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult
from app.events.event_models import AssistantAnnouncement
from app.events.notifier import AssistantNotifier
from app.config import ASSISTANT_SETTINGS
from app.session.state import session_state
from app.adaptive.history import register_negative_feedback
from app.providers.router import ProviderRouter
from app.custom_commands.admin import CustomCommandsAdmin
from app.dictation.state import dictation_state
from app.chat.state import chat_state


class CommandExecutor:
    def __init__(self):
        self.notifier = AssistantNotifier()
        self.provider_router = ProviderRouter()
        self.custom_admin = CustomCommandsAdmin()

    def execute(self, command: ParsedCommand, resolved: ResolvedTarget) -> ExecutionResult:
        if command.intent == "enable_chat_mode":
            chat_state.enable()
            self.notifier.say("Режим общения включён.")
            return ExecutionResult(
                success=True,
                message="Режим общения включён.",
                intent=command.intent
            )

        if command.intent == "disable_chat_mode":
            chat_state.disable()
            self.notifier.say("Режим общения выключен.")
            return ExecutionResult(
                success=True,
                message="Режим общения выключен.",
                intent=command.intent
            )

        if command.intent == "enable_dictation":
            dictation_state.enable()
            self.notifier.say("Режим диктовки включён.")
            return ExecutionResult(
                success=True,
                message="Режим диктовки включён.",
                intent=command.intent
            )

        if command.intent == "disable_dictation":
            dictation_state.disable()
            self.notifier.say("Режим диктовки выключен.")
            return ExecutionResult(
                success=True,
                message="Режим диктовки выключен.",
                intent=command.intent
            )

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

        if command.intent == "custom_command":
            row = self.custom_admin.resolve_command(command.normalized_text)
            if not row or not row["is_enabled"]:
                self.notifier.say("Пользовательская команда недоступна.")
                return ExecutionResult(
                    success=False,
                    message="Пользовательская команда недоступна.",
                    intent=command.intent
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
                        target_path=payload
                    )

                if command_type == "open_url":
                    self.notifier.say("Открываю ссылку.")
                    webbrowser.open(payload)
                    self.notifier.say_random("done")
                    return ExecutionResult(
                        success=True,
                        message=f"Открыта ссылка: {payload}",
                        intent=command.intent,
                        target_path=payload
                    )

                self.notifier.say("Неизвестный тип пользовательской команды.")
                return ExecutionResult(
                    success=False,
                    message=f"Неизвестный тип пользовательской команды: {command_type}",
                    intent=command.intent
                )
            except Exception as e:
                self.notifier.say("Не удалось выполнить пользовательскую команду.")
                return ExecutionResult(
                    success=False,
                    message=f"Ошибка выполнения пользовательской команды: {e}",
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