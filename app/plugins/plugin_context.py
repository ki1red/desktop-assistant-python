from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PluginContext:
    """
    Контекст команды, который передаётся аддонам.

    Это единая форма данных после STT, очистки текста
    и, если включено, AI-нормализации.
    """

    raw_text: str
    normalized_text: str
    language: str | None = None
    source: str = "voice"
    metadata: dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        """
        Возвращает основной текст команды.
        """
        return (self.normalized_text or self.raw_text or "").strip()

    def text_lower(self) -> str:
        """
        Возвращает текст команды в нижнем регистре.
        """
        return self.text().lower().replace("ё", "е")

    def has_text(self) -> bool:
        """
        Проверяет, есть ли вообще текст команды.
        """
        return bool(self.text())