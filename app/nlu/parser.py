import re

from app.models import ParsedCommand
from app.nlu.normalizer import normalize_command_text
from app.custom_commands.admin import CustomCommandsAdmin
from app.settings_service import settings_service
from app.plugins.settings import is_plugin_enabled
from app.logger import get_logger


logger = get_logger("parser")


def normalize_phrase_for_match(text: str) -> str:
    text = normalize_command_text(text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text


class CommandParser:
    """
    Временный совместимый parser.

    Он всё ещё использует старые списки ключевых фраз, но уже заполняет
    plugin_id, command_id, confidence и metadata внутри ParsedCommand.

    Это безопасный промежуточный слой перед полным переходом на PluginRegistry.
    """

    OPEN_FILE_KEYWORDS = [
        "открой файл",
        "открыть файл",
        "открою файл",
        "покажи файл",
        "показать файл",
        "найди файл",
        "найти файл",
    ]

    OPEN_FOLDER_KEYWORDS = [
        "открой папку",
        "открыть папку",
        "открою папку",
        "покажи папку",
        "показать папку",
        "найди папку",
        "найти папку",
    ]

    PLAY_MEDIA_KEYWORDS = [
        "включи песню",
        "включить песню",
        "найди песню",
        "найти песню",
        "включи музыку",
        "включить музыку",
        "поставь музыку",
        "поставь песню",
        "поставь трек",
        "воспроизведи",
    ]

    VIDEO_SEARCH_KEYWORDS = [
        "включи видео",
        "включить видео",
        "найди видео",
        "найти видео",
        "открой видео",
        "запусти видео",
    ]

    WEB_SEARCH_KEYWORDS = [
        "найди в браузере",
        "поиск в браузере",
        "найди в интернете",
        "найди в гугле",
        "загугли",
        "поищи в интернете",
        "поищи в гугле",
    ]

    YOUTUBE_SEARCH_KEYWORDS = [
        "найди на ютубе",
        "найди в ютубе",
        "поиск на ютубе",
        "открой на ютубе",
        "поищи на ютубе",
        "найди на youtube",
        "поищи на youtube",
    ]

    GENERIC_OPEN_KEYWORDS = [
        "открой",
        "открыть",
        "открою",
        "запусти",
        "запустить",
        "запущу",
        "включи",
        "включить",
        "покажи",
        "показать",
    ]

    NEGATIVE_FEEDBACK_KEYWORDS = [
        "ты ошибся",
        "не то",
        "не тот",
        "ошибка",
        "неправильно",
    ]

    DEEP_SEARCH_CONFIRM_KEYWORDS = [
        "да",
        "ищи",
        "ищи глубже",
        "ищи везде",
        "выполни глубокий поиск",
        "глубокий поиск",
    ]

    DEEP_SEARCH_REJECT_KEYWORDS = [
        "нет",
        "не ищи",
        "не надо",
        "отмена",
        "не нужно",
    ]

    DICTATION_ENABLE_KEYWORDS = [
        "включи диктовку",
        "включить диктовку",
        "режим диктовки",
        "начни диктовку",
        "начать диктовку",
        "включи режим диктовки",
        "включить режим диктовки",
    ]

    DICTATION_DISABLE_KEYWORDS = [
        "выключи диктовку",
        "выключить диктовку",
        "останови диктовку",
        "остановить диктовку",
        "заверши диктовку",
        "закончить диктовку",
        "выключи режим диктовки",
        "выключить режим диктовки",
    ]

    SELECTION_KEYWORDS = {
        "первый": 1,
        "первая": 1,
        "1": 1,
        "один": 1,
        "второй": 2,
        "вторая": 2,
        "2": 2,
        "два": 2,
        "третий": 3,
        "третья": 3,
        "3": 3,
        "три": 3,
    }

    TARGET_FILLER_WORDS = {
        "приложение",
        "приложения",
        "программа",
        "программу",
        "программы",
    }

    DEFAULT_WAKE_PHRASES = {
        "ассистент",
        "режим общения",
        "включи режим общения",
        "давай поговорим",
    }

    DEFAULT_STOP_PHRASES = {
        "выключи режим общения",
        "хватит общаться",
        "режим общения выключить",
        "заверши общение",
    }

    INTENT_PLUGIN_COMMAND_MAP = {
        "open_file": ("filesystem", "open_file"),
        "open_folder": ("filesystem", "open_folder"),
        "open_app": ("filesystem", "open_app"),
        "generic_open": ("filesystem", "open_anything"),

        "search_web": ("web", "search_web"),
        "search_youtube": ("web", "search_youtube"),

        "play_music_query": ("music", "play_music_query"),

        "enable_dictation": ("dictation", "enable_dictation"),
        "disable_dictation": ("dictation", "disable_dictation"),

        "enable_chat_mode": ("chat", "enable_chat_mode"),
        "disable_chat_mode": ("chat", "disable_chat_mode"),
    }

    def __init__(self):
        self.custom_admin = CustomCommandsAdmin()

    def _cleanup_target(self, target: str) -> str:
        """
        Убирает служебные слова из цели команды.
        """
        tokens = target.split()
        tokens = [t for t in tokens if t not in self.TARGET_FILLER_WORDS]
        return " ".join(tokens).strip()

    def _get_plugin_info(self, intent: str) -> tuple[str | None, str | None]:
        """
        Возвращает plugin_id и command_id для intent.
        """
        return self.INTENT_PLUGIN_COMMAND_MAP.get(intent, (None, None))

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

    def _make_command(
        self,
        raw_text: str,
        normalized: str,
        intent: str,
        target_text: str = "",
        confidence: float = 0.8,
        metadata: dict | None = None,
    ) -> ParsedCommand:
        """
        Создаёт ParsedCommand и добавляет plugin-поля.

        Если intent относится к выключенному плагину, команда превращается
        в unknown. Это нужно, чтобы отключённый filesystem/web/music/chat
        не продолжал выполнять действия через старый pipeline.
        """
        plugin_id, command_id = self._get_plugin_info(intent)
        data = dict(metadata or {})

        if plugin_id:
            data["plugin_id"] = plugin_id
            data["command_id"] = command_id

            if not is_plugin_enabled(plugin_id, default=True):
                logger.info(
                    "PARSER matched disabled plugin | intent=%s plugin=%s command=%s",
                    intent,
                    plugin_id,
                    command_id,
                )

                return self._make_unknown(
                    raw_text=raw_text,
                    normalized=normalized,
                    target_text=target_text,
                    reason=f"Плагин выключен: {plugin_id}",
                    metadata={
                        "disabled_plugin_id": plugin_id,
                        "disabled_command_id": command_id,
                        "original_intent": intent,
                    },
                )

        return ParsedCommand(
            raw_text=raw_text,
            normalized_text=normalized,
            intent=intent,
            target_text=target_text,
            plugin_id=plugin_id,
            command_id=command_id,
            confidence=confidence,
            metadata=data,
        )

    def _fallback_intent(self, raw_text: str, normalized: str) -> ParsedCommand:
        """
        Последний fallback, если явная команда не найдена.

        Короткие фразы считаем попыткой открыть объект.
        Средние фразы считаем веб-запросом.
        Но только если соответствующий плагин включён.
        """
        words = normalized.split()

        if 1 <= len(words) <= 3:
            if is_plugin_enabled("filesystem", default=True):
                logger.info("PARSER fallback -> generic_open | normalized=%s", normalized)
                return self._make_command(
                    raw_text=raw_text,
                    normalized=normalized,
                    intent="generic_open",
                    target_text=normalized,
                    confidence=0.35,
                    metadata={"match_type": "fallback_short_text"},
                )

            logger.info("PARSER fallback generic_open skipped: filesystem disabled")
            return self._make_unknown(
                raw_text=raw_text,
                normalized=normalized,
                target_text=normalized,
                reason="Файловый плагин выключен.",
            )

        if 3 <= len(words) <= 6:
            if is_plugin_enabled("web", default=True):
                logger.info("PARSER fallback -> search_web | normalized=%s", normalized)
                return self._make_command(
                    raw_text=raw_text,
                    normalized=normalized,
                    intent="search_web",
                    target_text=normalized,
                    confidence=0.35,
                    metadata={"match_type": "fallback_medium_text"},
                )

            logger.info("PARSER fallback search_web skipped: web disabled")
            return self._make_unknown(
                raw_text=raw_text,
                normalized=normalized,
                target_text=normalized,
                reason="Веб-плагин выключен.",
            )

        logger.info("PARSER fallback -> unknown | normalized=%s", normalized)
        return self._make_unknown(
            raw_text=raw_text,
            normalized=normalized,
            target_text=normalized,
            reason="Команда не распознана.",
        )

    def _get_wake_phrases(self) -> set[str]:
        """
        Возвращает фразы включения режима общения.

        Пока они остаются в ai-настройках для совместимости.
        Позже перенесём их в chat plugin.
        """
        ai_cfg = settings_service.get_section("ai", {})
        raw = ai_cfg.get("wake_phrases", [])
        if not raw:
            raw = list(self.DEFAULT_WAKE_PHRASES)
        return {normalize_phrase_for_match(p) for p in raw if p}

    def _get_stop_phrases(self) -> set[str]:
        """
        Возвращает фразы выключения режима общения.

        Пока они остаются в ai-настройках для совместимости.
        Позже перенесём их в chat plugin.
        """
        ai_cfg = settings_service.get_section("ai", {})
        raw = ai_cfg.get("stop_phrases", [])
        if not raw:
            raw = list(self.DEFAULT_STOP_PHRASES)
        return {normalize_phrase_for_match(p) for p in raw if p}

    def parse(self, text: str) -> ParsedCommand:
        normalized = normalize_command_text(text)
        normalized_for_match = normalize_phrase_for_match(text)

        wake_phrases = self._get_wake_phrases()
        stop_phrases = self._get_stop_phrases()

        logger.info(
            "PARSER input | raw=%r | normalized=%r | normalized_for_match=%r",
            text,
            normalized,
            normalized_for_match,
        )
        logger.info("PARSER wake_phrases=%s", sorted(wake_phrases))
        logger.info("PARSER stop_phrases=%s", sorted(stop_phrases))

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

        if normalized in self.SELECTION_KEYWORDS:
            logger.info("PARSER matched select_candidate")
            return ParsedCommand(
                raw_text=text,
                normalized_text=normalized,
                intent="select_candidate",
                target_text=str(self.SELECTION_KEYWORDS[normalized]),
                plugin_id=None,
                command_id="select_candidate",
                confidence=0.9,
                metadata={"match_type": "legacy_selection"},
            )

        if normalized_for_match in wake_phrases:
            logger.info("PARSER matched enable_chat_mode")
            return self._make_command(
                raw_text=text,
                normalized=normalized,
                intent="enable_chat_mode",
                target_text="",
                confidence=0.95,
                metadata={"match_type": "chat_wake_phrase"},
            )

        if normalized_for_match in stop_phrases:
            logger.info("PARSER matched disable_chat_mode")
            return self._make_command(
                raw_text=text,
                normalized=normalized,
                intent="disable_chat_mode",
                target_text="",
                confidence=0.95,
                metadata={"match_type": "chat_stop_phrase"},
            )

        if normalized in self.DICTATION_ENABLE_KEYWORDS:
            logger.info("PARSER matched enable_dictation")
            return self._make_command(
                raw_text=text,
                normalized=normalized,
                intent="enable_dictation",
                target_text="",
                confidence=0.95,
                metadata={"match_type": "dictation_enable_exact"},
            )

        if normalized in self.DICTATION_DISABLE_KEYWORDS:
            logger.info("PARSER matched disable_dictation")
            return self._make_command(
                raw_text=text,
                normalized=normalized,
                intent="disable_dictation",
                target_text="",
                confidence=0.95,
                metadata={"match_type": "dictation_disable_exact"},
            )

        if normalized in self.DEEP_SEARCH_CONFIRM_KEYWORDS:
            logger.info("PARSER matched confirm_deep_search")
            return ParsedCommand(
                raw_text=text,
                normalized_text=normalized,
                intent="confirm_deep_search",
                target_text="",
                plugin_id=None,
                command_id="confirm_deep_search",
                confidence=0.8,
                metadata={"match_type": "legacy_deep_search_confirm"},
            )

        if normalized in self.DEEP_SEARCH_REJECT_KEYWORDS:
            logger.info("PARSER matched reject_deep_search")
            return ParsedCommand(
                raw_text=text,
                normalized_text=normalized,
                intent="reject_deep_search",
                target_text="",
                plugin_id=None,
                command_id="reject_deep_search",
                confidence=0.8,
                metadata={"match_type": "legacy_deep_search_reject"},
            )

        for phrase in self.NEGATIVE_FEEDBACK_KEYWORDS:
            if normalized == phrase or normalized.startswith(phrase):
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

        for prefix in self.WEB_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                logger.info(
                    "PARSER matched search_web | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="search_web",
                    target_text=target,
                    confidence=0.9,
                    metadata={"match_type": "prefix", "prefix": prefix},
                )

        for prefix in self.YOUTUBE_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                logger.info(
                    "PARSER matched search_youtube | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="search_youtube",
                    target_text=target,
                    confidence=0.9,
                    metadata={"match_type": "prefix", "prefix": prefix},
                )

        for prefix in self.VIDEO_SEARCH_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info(
                    "PARSER matched video->search_youtube | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="search_youtube",
                    target_text=target,
                    confidence=0.85,
                    metadata={"match_type": "video_prefix_to_youtube", "prefix": prefix},
                )

        for prefix in self.OPEN_FILE_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info(
                    "PARSER matched open_file | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="open_file",
                    target_text=target,
                    confidence=0.9,
                    metadata={"match_type": "prefix", "prefix": prefix},
                )

        for prefix in self.OPEN_FOLDER_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info(
                    "PARSER matched open_folder | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="open_folder",
                    target_text=target,
                    confidence=0.9,
                    metadata={"match_type": "prefix", "prefix": prefix},
                )

        for prefix in self.PLAY_MEDIA_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info(
                    "PARSER matched play_music_query | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="play_music_query",
                    target_text=target,
                    confidence=0.9,
                    metadata={"match_type": "prefix", "prefix": prefix},
                )

        for prefix in self.GENERIC_OPEN_KEYWORDS:
            if normalized.startswith(prefix):
                target = normalized.replace(prefix, "", 1).strip()
                target = self._cleanup_target(target)
                logger.info(
                    "PARSER matched generic_open | prefix=%s | target=%s",
                    prefix,
                    target,
                )
                return self._make_command(
                    raw_text=text,
                    normalized=normalized,
                    intent="generic_open",
                    target_text=target,
                    confidence=0.75,
                    metadata={"match_type": "generic_open_prefix", "prefix": prefix},
                )

        return self._fallback_intent(text, normalized)