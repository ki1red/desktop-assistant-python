from app.plugins.base import AssistantPlugin
from app.plugins.command_models import PluginCommandSpec, PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult

from app.nlu.parser import CommandParser
from app.resolver.resolver import TargetResolver
from app.executor.executor import CommandExecutor
from app.models import ResolvedTarget
from app.adaptive.history import save_usage
from app.adaptive.quick_access import upsert_quick_target
from app.session.state import session_state
from app.runtime_control import runtime_control


class FileSystemPlugin(AssistantPlugin):
    """
    Встроенный аддон файловой системы.

    Он временно использует старые parser/resolver/executor,
    но уже работает как отдельный аддон.
    """

    plugin_id = "filesystem"
    title = "Файловая система"
    description = "Открытие приложений, файлов и папок на компьютере."
    default_enabled = True

    SUPPORTED_INTENTS = {
        "generic_open",
        "open_file",
        "open_folder",
        "open_app",
    }

    def __init__(self):
        """
        Создаёт файловый аддон и старые сервисы поиска.
        """
        super().__init__()
        self.parser = CommandParser()
        self.resolver = TargetResolver()
        self.executor = CommandExecutor()

    def get_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает команды файлового аддона.
        """
        return [
            PluginCommandSpec(
                plugin_id=self.plugin_id,
                command_id="open_anything",
                title="Открыть приложение, файл или папку",
                description="Открывает первый наиболее подходящий объект из индекса.",
                examples=[
                    "открой стим",
                    "запусти пайчарм",
                    "открой папку документы",
                    "найди файл отчёт",
                ],
                keywords=[
                    "открой",
                    "открыть",
                    "запусти",
                    "запустить",
                    "покажи",
                    "найди файл",
                    "открой папку",
                    "запусти приложение",
                ],
                intent_hints=[
                    "generic_open",
                    "open_file",
                    "open_folder",
                    "open_app",
                ],
                priority=90,
            ),
        ]

    def match(self, context: PluginContext) -> PluginMatch:
        """
        Проверяет, похожа ли команда на открытие файла, папки или приложения.
        """
        text = context.text_lower()

        if not text:
            return PluginMatch(self.plugin_id, "", 0.0, "Пустой текст.")

        command = self.parser.parse(text)

        if command.intent in self.SUPPORTED_INTENTS:
            return PluginMatch(
                plugin_id=self.plugin_id,
                command_id="open_anything",
                score=0.92,
                reason=f"Старый parser распознал intent={command.intent}",
                metadata={"parsed_command": command},
            )

        base_match = super().match(context)

        return base_match

    def _auto_pick_first_candidate(self, resolved: ResolvedTarget) -> ResolvedTarget:
        """
        Если resolver просит подтверждение, автоматически выбирает первый вариант.
        """
        if not resolved.needs_confirmation or not resolved.candidates:
            return resolved

        best = resolved.candidates[0]

        self.logger.info(
            "Автовыбор первого кандидата: name=%s path=%s type=%s",
            best.name,
            best.path,
            best.target_type,
        )

        return ResolvedTarget(
            success=True,
            target_type=best.target_type,
            target_name=best.name,
            target_path=best.path,
            candidates=resolved.candidates,
        )

    def _save_adaptive_result(self, command, resolved: ResolvedTarget, execution):
        """
        Сохраняет историю использования для адаптивности.
        """
        save_usage(
            query_text=command.target_text,
            intent=command.intent,
            target_name=resolved.target_name or "",
            target_path=resolved.target_path or "",
            target_type=resolved.target_type or "",
            success=execution.success,
        )

        if execution.success and resolved.target_path and resolved.target_name and resolved.target_type:
            upsert_quick_target(
                name=resolved.target_name,
                target_path=resolved.target_path,
                target_type=resolved.target_type,
                provider="filesystem",
                increment_usage=True,
            )

        session_state.remember(command, resolved, execution)

    def handle(self, context: PluginContext, match: PluginMatch | None = None) -> PluginResult:
        """
        Выполняет открытие приложения, файла или папки.
        """
        if runtime_control.is_cancelled():
            return PluginResult.fail(
                "Операция отменена пользователем.",
                self.plugin_id,
                "open_anything",
                intent="generic_open",
            )

        command = None

        if match and match.metadata.get("parsed_command"):
            command = match.metadata["parsed_command"]
        else:
            command = self.parser.parse(context.text())

        if command.intent not in self.SUPPORTED_INTENTS:
            return PluginResult.not_handled(self.plugin_id)

        self.logger.info(
            "Файловый аддон выполняет команду: intent=%s target=%s",
            command.intent,
            command.target_text,
        )

        resolved = self.resolver.resolve(command, deep_search=False)

        if resolved.suggests_deep_search:
            self.logger.info("Быстрый поиск ничего не дал. Запускаю deep_search автоматически.")
            resolved = self.resolver.resolve(command, deep_search=True)

        resolved = self._auto_pick_first_candidate(resolved)

        execution = self.executor.execute(command, resolved)

        try:
            self._save_adaptive_result(command, resolved, execution)
        except Exception as e:
            self.logger.exception("Не удалось сохранить адаптивную историю: %s", e)

        return PluginResult(
            handled=True,
            success=execution.success,
            message=execution.message,
            intent=execution.intent or command.intent,
            plugin_id=self.plugin_id,
            command_id="open_anything",
        )