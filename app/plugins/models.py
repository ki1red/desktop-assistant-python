from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PluginCommand:
    """
    Описание команды плагина для этапа распознавания.

    Это не выполняющий класс, а чистое описание:
    какие фразы относятся к какому plugin_id, command_id и intent.
    """

    plugin_id: str
    command_id: str
    intent: str
    title: str

    exact_phrases: list[str] = field(default_factory=list)
    prefixes: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    target_fillers: list[str] = field(default_factory=list)

    # Если True, команда с префиксом без цели не считается выполненной.
    # Например: "найди в интернете" без запроса не должен открывать пустой поиск.
    requires_target: bool = True

    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginDefinition:
    """
    Описание плагина для registry.

    Пока здесь только данные, нужные parser.
    Позже сюда можно добавить:
    - описание вкладки UI;
    - настройки плагина;
    - путь к ресурсам;
    - путь к отдельной БД.
    """

    plugin_id: str
    title: str
    description: str = ""
    default_enabled: bool = True
    commands: list[PluginCommand] = field(default_factory=list)


@dataclass(slots=True)
class PluginMatch:
    """
    Результат сопоставления текста пользователя с командой плагина.
    """

    plugin_id: str
    command_id: str
    intent: str
    target_text: str = ""
    confidence: float = 0.0
    match_type: str = ""
    matched_phrase: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_good(self, threshold: float = 0.45) -> bool:
        """
        Проверяет, достаточно ли уверенно распознана команда.
        """
        return self.confidence >= threshold