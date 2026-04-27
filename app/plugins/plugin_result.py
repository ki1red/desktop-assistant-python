from dataclasses import dataclass, field
from typing import Any

from app.models import ExecutionResult


@dataclass(slots=True)
class PluginResult:
    """
    Универсальный результат выполнения команды аддоном.

    Потом он преобразуется в стандартный ExecutionResult,
    который уже умеет показывать старый presenter.
    """

    handled: bool
    success: bool = False
    message: str = ""
    intent: str = "plugin"
    plugin_id: str = ""
    command_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def not_handled(cls, plugin_id: str = ""):
        """
        Возвращает результат, если аддон не подходит для команды.
        """
        return cls(
            handled=False,
            success=False,
            message="",
            intent="plugin_not_handled",
            plugin_id=plugin_id,
        )

    @classmethod
    def ok(cls, message: str, plugin_id: str, command_id: str, intent: str = "plugin"):
        """
        Создаёт успешный результат выполнения команды.
        """
        return cls(
            handled=True,
            success=True,
            message=message,
            intent=intent,
            plugin_id=plugin_id,
            command_id=command_id,
        )

    @classmethod
    def fail(cls, message: str, plugin_id: str, command_id: str = "", intent: str = "plugin"):
        """
        Создаёт результат с ошибкой выполнения команды.
        """
        return cls(
            handled=True,
            success=False,
            message=message,
            intent=intent,
            plugin_id=plugin_id,
            command_id=command_id,
        )

    def to_execution_result(self) -> ExecutionResult:
        """
        Преобразует PluginResult в старый ExecutionResult.
        """
        return ExecutionResult(
            success=self.success,
            message=self.message,
            intent=self.intent,
        )