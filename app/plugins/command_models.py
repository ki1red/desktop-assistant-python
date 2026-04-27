from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PluginCommandSpec:
    """
    Описание команды, которую умеет выполнять аддон.

    Эти данные нужны роутеру и ИИ, чтобы понимать:
    - какой аддон умеет выполнять команду;
    - какие фразы похожи на эту команду;
    - какой command_id нужно вернуть при выборе команды.
    """

    plugin_id: str
    command_id: str
    title: str
    description: str = ""
    examples: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    intent_hints: list[str] = field(default_factory=list)
    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginMatch:
    """
    Результат проверки: насколько аддон подходит под фразу пользователя.
    """

    plugin_id: str
    command_id: str
    score: float
    reason: str = ""
    spec: PluginCommandSpec | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_good(self, threshold: float = 0.45) -> bool:
        """
        Проверяет, достаточно ли уверенное совпадение.
        """
        return self.score >= threshold