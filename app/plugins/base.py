from abc import ABC, abstractmethod

from app.plugins.command_models import PluginCommandSpec, PluginMatch
from app.plugins.plugin_context import PluginContext
from app.plugins.plugin_result import PluginResult
from app.plugins.settings import is_plugin_enabled
from app.logger import get_logger


class AssistantPlugin(ABC):
    """
    Базовый класс любого плагина ассистента.

    Каждый плагин должен:
    - иметь plugin_id;
    - отдавать список команд;
    - уметь оценивать, подходит ли ему фраза;
    - уметь выполнять команду.
    """

    plugin_id = "base"
    title = "Базовый плагин"
    description = ""
    default_enabled = True

    def __init__(self):
        """
        Создаёт плагин и отдельный логгер для него.
        """
        self.logger = get_logger(f"plugin.{self.plugin_id}")

    def is_enabled(self) -> bool:
        """
        Проверяет, включён ли плагин в настройках пользователя.

        Новый основной формат:
        plugins.enabled.<plugin_id>

        Старый формат assistant.enabled_plugins поддерживается внутри
        app.plugins.settings для мягкого перехода.
        """
        return is_plugin_enabled(
            plugin_id=self.plugin_id,
            default=bool(self.default_enabled),
        )

    def get_settings_widget(self):
        """
        Возвращает виджет настроек плагина.

        Пока возвращает None. Позже плагины смогут создавать свои вкладки.
        """
        return None

    @abstractmethod
    def get_command_specs(self) -> list[PluginCommandSpec]:
        """
        Возвращает список команд, которые поддерживает плагин.
        """
        raise NotImplementedError

    def match(self, context: PluginContext) -> PluginMatch:
        """
        Базовая эвристика совпадения команды с плагином.

        Плагин может переопределить этот метод, если нужна более умная логика.
        """
        text = context.text_lower()

        if not text:
            return PluginMatch(
                plugin_id=self.plugin_id,
                command_id="",
                score=0.0,
                reason="Пустая команда.",
            )

        best_match = PluginMatch(
            plugin_id=self.plugin_id,
            command_id="",
            score=0.0,
            reason="Совпадение не найдено.",
        )

        for spec in self.get_command_specs():
            score = self._score_spec(text, spec)

            if score > best_match.score:
                best_match = PluginMatch(
                    plugin_id=self.plugin_id,
                    command_id=spec.command_id,
                    score=score,
                    reason=f"Совпадение по описанию команды: {spec.title}",
                    spec=spec,
                )

        return best_match

    def _score_spec(self, text: str, spec: PluginCommandSpec) -> float:
        """
        Считает простую оценку совпадения текста с командой.
        """
        score = 0.0

        for keyword in spec.keywords:
            key = keyword.lower().replace("ё", "е").strip()
            if key and key in text:
                score += 0.25

        for example in spec.examples:
            ex = example.lower().replace("ё", "е").strip()
            if not ex:
                continue

            prefix = ex.split("...")[0].strip()
            if prefix and text.startswith(prefix):
                score += 0.35

        for hint in spec.intent_hints:
            hint = hint.lower().strip()
            if hint and hint in text:
                score += 0.2

        score += min(max(spec.priority, 0), 100) / 1000.0

        return min(score, 1.0)

    @abstractmethod
    def handle(self, context: PluginContext, match: PluginMatch | None = None) -> PluginResult:
        """
        Выполняет команду плагина.
        """
        raise NotImplementedError