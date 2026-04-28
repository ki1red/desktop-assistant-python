from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text
from app.custom_commands.admin import CustomCommandsAdmin
from app.plugins.registry import PluginRegistry
from app.plugins.registry import normalize_phrase_for_match as plugin_normalize_phrase_for_match
from app.logger import get_logger


logger = get_logger("parser")


def normalize_phrase_for_match(text: str) -> str:
    """
    Совместимая функция нормализации.

    Оставлена здесь, потому что её могут импортировать старые части проекта.
    Реальная логика теперь находится в app.plugins.registry.
    """
    return plugin_normalize_phrase_for_match(text)


class CommandParser:
    """
    Parser переходного этапа.

    Основное распознавание команд идёт через PluginRegistry.
    """

    NEGATIVE_FEEDBACK_KEYWORDS = [
        "ты ошибся",
        "не то",
        "не тот",
        "ошибка",
        "неправильно",
    ]

    def __init__(self):
        self.custom_admin = CustomCommandsAdmin()
        self.plugin_registry = PluginRegistry()

    def _make_unknown(
        self,
        raw_text: str,
        normalized: str,
        target_text: str = "",
        reason: str = "",
        metadata: dict | None = None,
    ) -> ParsedCommand:
        """
        Создаёт команду unknown.
        """
        data = dict(metadata or {})
        if reason:
            data["reason"] = reason

        return ParsedCommand(
            raw_text=raw_text,
            normalized_text=normalized,
            intent="unknown",
            target_text=target_text,
            plugin_id=None,
            command_id=None,
            confidence=0.0,
            metadata=data,
        )

    def _make_incomplete_command(
        self,
        raw_text: str,
        normalized: str,
        target_text: str,
    ) -> ParsedCommand:
        """
        Создаёт команду для неполного запроса.

        Например:
        - "найди в интернете"
        - "в интернете"
        - "включи музыку"
        """
        return ParsedCommand(
            raw_text=raw_text,
            normalized_text=normalized,
            intent="incomplete_command",
            target_text=target_text,
            plugin_id=None,
            command_id="incomplete_command",
            confidence=0.4,
            metadata={
                "match_type": "incomplete_command",
                "reason": "Командный префикс распознан, но цель команды отсутствует.",
            },
        )

    def _make_command_from_plugin_match(
        self,
        raw_text: str,
        normalized: str,
        match,
    ) -> ParsedCommand:
        """
        Преобразует PluginMatch в ParsedCommand.
        """
        metadata = dict(match.metadata or {})
        metadata.update({
            "match_type": match.match_type,
            "matched_phrase": match.matched_phrase,
            "reason": match.reason,
        })

        return ParsedCommand(
            raw_text=raw_text,
            normalized_text=normalized,
            intent=match.intent,
            target_text=match.target_text,
            plugin_id=match.plugin_id,
            command_id=match.command_id,
            confidence=match.confidence,
            metadata=metadata,
        )

    def _is_negative_feedback(self, normalized: str) -> bool:
        """
        Проверяет фразы негативной обратной связи.
        """
        for phrase in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if normalized == phrase or normalized.startswith(phrase):
                return True

        return False

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)
        normalized_for_match = normalize_phrase_for_match(text)

        logger.info(
            "PARSER input | raw=%r | normalized=%r | normalized_for_match=%r",
            text,
            normalized,
            normalized_for_match,
        )

        custom = self.custom_admin.resolve_command(normalized)
        if custom and custom["is_enabled"]:
            logger.info("PARSER matched custom_command")
            return ParsedCommand(
                raw_text=text,
                normalized_text=normalized,
                intent="custom_command",
                target_text=normalized,
                plugin_id=None,
                command_id="custom_command",
                confidence=0.95,
                metadata={"match_type": "custom_command"},
            )

        if self._is_negative_feedback(normalized):
            logger.info("PARSER matched negative_feedback")
            return ParsedCommand(
                raw_text=text,
                normalized_text=normalized,
                intent="negative_feedback",
                target_text="",
                plugin_id=None,
                command_id="negative_feedback",
                confidence=0.8,
                metadata={"match_type": "legacy_negative_feedback"},
            )

        plugin_match = self.plugin_registry.match(text)
        if plugin_match:
            logger.info(
                "PARSER plugin match | plugin=%s command=%s intent=%s target=%s confidence=%.3f",
                plugin_match.plugin_id,
                plugin_match.command_id,
                plugin_match.intent,
                plugin_match.target_text,
                plugin_match.confidence,
            )
            return self._make_command_from_plugin_match(
                raw_text=text,
                normalized=normalized,
                match=plugin_match,
            )

        if self.plugin_registry.is_incomplete_command_text(text):
            logger.info(
                "PARSER incomplete command | text=%s normalized_for_match=%s",
                text,
                normalized_for_match,
            )
            return self._make_incomplete_command(
                raw_text=text,
                normalized=normalized,
                target_text=normalized_for_match,
            )

        fallback_match = self.plugin_registry.fallback(text)
        if fallback_match:
            logger.info(
                "PARSER plugin fallback | plugin=%s command=%s intent=%s target=%s confidence=%.3f",
                fallback_match.plugin_id,
                fallback_match.command_id,
                fallback_match.intent,
                fallback_match.target_text,
                fallback_match.confidence,
            )
            return self._make_command_from_plugin_match(
                raw_text=text,
                normalized=normalized,
                match=fallback_match,
            )

        logger.info("PARSER fallback -> unknown | normalized=%s", normalized)

        return self._make_unknown(
            raw_text=text,
            normalized=normalized,
            target_text=normalized,
            reason="Команда не распознана ни одним включённым плагином.",
            metadata={"match_type": "unknown"},
        )