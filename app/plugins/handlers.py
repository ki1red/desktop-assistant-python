from dataclasses import dataclass
from typing import Any, Callable

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult


@dataclass
class PluginExecutionContext:
    """
    Контекст выполнения команды плагина.

    Через него handler получает общие сервисы executor-а,
    но не создаёт их сам.
    """
    notifier: Any
    provider_router: Any
    safe_user_error: Callable[[str | None], str]
    target_required_error: Callable[[str], ExecutionResult]


class PluginCommandHandler:
    """
    Базовый класс handler-а команды плагина.

    Каждый handler отвечает за один plugin_id.
    """

    plugin_id: str = ""
    supported_intents: set[str] = set()
    supported_command_ids: set[str] = set()

    def can_handle(self, command: ParsedCommand) -> bool:
        """
        Проверяет, может ли handler выполнить команду.
        """
        if command.intent in self.supported_intents:
            return True

        if command.plugin_id == self.plugin_id and command.command_id in self.supported_command_ids:
            return True

        return False

    def execute(
        self,
        command: ParsedCommand,
        resolved: ResolvedTarget,
        context: PluginExecutionContext,
    ) -> ExecutionResult:
        """
        Выполняет команду плагина.
        """
        raise NotImplementedError