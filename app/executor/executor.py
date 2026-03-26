import os

from app.models import ParsedCommand, ResolvedTarget, ExecutionResult


class CommandExecutor:
    def execute(self, command: ParsedCommand, resolved: ResolvedTarget) -> ExecutionResult:
        if not resolved.success or not resolved.target_path:
            return ExecutionResult(
                success=False,
                message=resolved.error or "Цель не была найдена.",
                intent=command.intent
            )

        try:
            os.startfile(resolved.target_path)

            return ExecutionResult(
                success=True,
                message=f"Успешно выполнено: {command.intent} -> {resolved.target_path}",
                intent=command.intent,
                target_path=resolved.target_path
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Ошибка выполнения: {e}",
                intent=command.intent,
                target_path=resolved.target_path
            )