import re

from app.logger import get_logger
from app.nlu.normalizer import normalize_command_text
from app.plugins.models import PluginCommand, PluginDefinition, PluginMatch
from app.plugins.resources import load_builtin_plugin_definitions
from app.plugins.settings import is_plugin_enabled


logger = get_logger("plugin_registry")


TARGET_FILLER_WORDS = {
    "приложение",
    "приложения",
    "программа",
    "программу",
    "программы",
}


COMMAND_START_REPLACEMENTS = {
    "включим": "включи",
    "выключим": "выключи",
    "откроем": "открой",
    "запустим": "запусти",
    "найдем": "найди",
    "найдём": "найди",
    "поищем": "поищи",
    "поставим": "поставь",
    "начнем": "начни",
    "начнём": "начни",
    "остановим": "останови",
    "завершим": "заверши",
}


COMMAND_START_WORDS = {
    "открой",
    "открыть",
    "открою",
    "запусти",
    "запустить",
    "запущу",
    "найди",
    "найти",
    "поищи",
    "поиск",
    "загугли",
    "погугли",
    "включи",
    "включить",
    "поставь",
    "воспроизведи",
    "покажи",
    "показать",
    "начни",
    "начать",
    "выключи",
    "выключить",
    "останови",
    "остановить",
    "заверши",
    "закончить",
}


WEB_SERVICE_WORDS = {
    "в",
    "на",
    "интернете",
    "интернет",
    "браузере",
    "браузер",
    "гугле",
    "гугл",
    "google",
    "ютубе",
    "ютуб",
    "youtube",
}


MUSIC_SERVICE_WORDS = {
    "музыка",
    "музыку",
    "музыки",
    "песня",
    "песню",
    "песни",
    "трек",
    "треки",
    "треков",
}


INCOMPLETE_SERVICE_TEXTS = {
    "найди в интернете",
    "поищи в интернете",
    "поиск в интернете",
    "найди в браузере",
    "поищи в браузере",
    "поиск в браузере",
    "найди в гугле",
    "поищи в гугле",
    "загугли",
    "погугли",
    "в интернете",
    "в браузере",
    "в гугле",
    "интернет",
    "браузер",
    "гугл",
    "google",

    "найди на ютубе",
    "поищи на ютубе",
    "поиск на ютубе",
    "открой на ютубе",
    "найди на youtube",
    "поищи на youtube",
    "на ютубе",
    "в ютубе",
    "на youtube",
    "в youtube",
    "ютуб",
    "youtube",

    "включи музыку",
    "включить музыку",
    "найди музыку",
    "найти музыку",
    "поставь музыку",
    "включи песню",
    "включить песню",
    "найди песню",
    "найти песню",
    "поставь песню",
    "поставь трек",
    "музыка",
    "музыку",
    "песня",
    "песню",
    "трек",
}


def _normalize_common_stt_command_variants(text: str) -> str:
    """
    Исправляет частые ошибки STT только в первом слове команды.
    """
    tokens = (text or "").split()
    if not tokens:
        return text

    first = tokens[0].lower()
    if first in COMMAND_START_REPLACEMENTS:
        tokens[0] = COMMAND_START_REPLACEMENTS[first]

    return " ".join(tokens)


def normalize_phrase_for_match(text: str) -> str:
    """
    Нормализация фразы для сопоставления команд.
    """
    text = normalize_command_text(text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    text = _normalize_common_stt_command_variants(text)
    return text


def _cleanup_target(target: str, fillers: list[str] | None = None) -> str:
    """
    Убирает служебные слова из цели команды.
    """
    filler_set = set(TARGET_FILLER_WORDS)
    filler_set.update(fillers or [])

    tokens = (target or "").split()
    tokens = [token for token in tokens if token not in filler_set]

    return " ".join(tokens).strip()


def _cleanup_keyword_target(normalized_text: str, command: PluginCommand, matched_keyword: str) -> str:
    """
    Чистит target для слабого keyword-match.

    Пример:
    "включи музыка куин" -> "куин"
    """
    text = (normalized_text or "").strip()
    tokens = text.split()

    if not tokens:
        return ""

    first = tokens[0]
    has_command_start = first in COMMAND_START_WORDS

    if not has_command_start:
        return text

    cleaned_tokens = []
    service_words = set(command.target_fillers or [])

    if command.plugin_id == "web":
        service_words.update(WEB_SERVICE_WORDS)
    elif command.plugin_id == "music":
        service_words.update(MUSIC_SERVICE_WORDS)

    service_words.add(matched_keyword)

    for token in tokens:
        if token in COMMAND_START_WORDS:
            continue
        if token in service_words:
            continue
        cleaned_tokens.append(token)

    return " ".join(cleaned_tokens).strip()


def _normalize_phrases(items: list[str]) -> list[str]:
    """
    Нормализует список фраз и убирает пустые значения.
    """
    result = []

    for item in items or []:
        normalized = normalize_phrase_for_match(item)
        if normalized:
            result.append(normalized)

    return sorted(set(result), key=lambda x: (-len(x), x))


class PluginRegistry:
    """
    Реестр команд плагинов для этапа parser.

    Сами команды теперь загружаются из app/plugins/builtin/commands.json.
    """

    def __init__(self):
        self._definitions = self._build_builtin_definitions()

    def _build_builtin_definitions(self) -> list[PluginDefinition]:
        """
        Загружает встроенные плагины из JSON-ресурса.
        """
        return load_builtin_plugin_definitions()

    def reload(self):
        """
        Пересобирает встроенные определения команд.
        """
        self._definitions = self._build_builtin_definitions()

    def get_all_definitions(self) -> list[PluginDefinition]:
        """
        Возвращает все известные плагины.
        """
        return list(self._definitions)

    def get_enabled_definitions(self) -> list[PluginDefinition]:
        """
        Возвращает только включённые плагины.
        """
        result = []

        for definition in self._definitions:
            if is_plugin_enabled(definition.plugin_id, definition.default_enabled):
                result.append(definition)

        return result

    def get_all_commands(self) -> list[PluginCommand]:
        """
        Возвращает команды включённых плагинов.
        """
        commands: list[PluginCommand] = []

        for definition in self.get_enabled_definitions():
            commands.extend(definition.commands)

        return commands

    def is_incomplete_command_text(self, text: str) -> bool:
        """
        Проверяет, является ли текст командным префиксом без цели.
        """
        normalized = normalize_phrase_for_match(text)
        if not normalized:
            return False

        if normalized in INCOMPLETE_SERVICE_TEXTS:
            return True

        for command in self.get_all_commands():
            if not command.requires_target:
                continue

            for prefix in _normalize_phrases(command.prefixes):
                if normalized == prefix:
                    return True

        return False

    def match(self, text: str) -> PluginMatch | None:
        """
        Ищет лучшее совпадение среди команд включённых плагинов.
        """
        normalized = normalize_phrase_for_match(text)

        if not normalized:
            return None

        matches: list[PluginMatch] = []

        for command in self.get_all_commands():
            exact_match = self._match_exact(normalized, command)
            if exact_match:
                matches.append(exact_match)

            prefix_match = self._match_prefix(normalized, command)
            if prefix_match:
                matches.append(prefix_match)

            keyword_match = self._match_keyword(normalized, command)
            if keyword_match:
                matches.append(keyword_match)

        if not matches:
            return None

        matches.sort(
            key=lambda item: (
                item.confidence,
                self._get_command_priority(item),
                len(item.matched_phrase or ""),
            ),
            reverse=True,
        )

        best = matches[0]

        logger.info(
            "PluginRegistry matched | plugin=%s command=%s intent=%s confidence=%.3f type=%s phrase=%s target=%s",
            best.plugin_id,
            best.command_id,
            best.intent,
            best.confidence,
            best.match_type,
            best.matched_phrase,
            best.target_text,
        )

        return best

    def fallback(self, text: str) -> PluginMatch | None:
        """
        Последний fallback, если явная команда не найдена.
        """
        normalized = normalize_phrase_for_match(text)
        words = normalized.split()

        if not normalized:
            return None

        if self.is_incomplete_command_text(normalized):
            logger.info("PluginRegistry fallback skipped: incomplete command text=%s", normalized)
            return None

        if 1 <= len(words) <= 3 and is_plugin_enabled("filesystem", True):
            return PluginMatch(
                plugin_id="filesystem",
                command_id="open_anything",
                intent="generic_open",
                target_text=normalized,
                confidence=0.35,
                match_type="fallback_short_text",
                reason="Короткая фраза без явной команды считается локальным открытием.",
                metadata={"source": "plugin_registry_fallback"},
            )

        if 3 <= len(words) <= 6 and is_plugin_enabled("web", True):
            return PluginMatch(
                plugin_id="web",
                command_id="search_web",
                intent="search_web",
                target_text=normalized,
                confidence=0.35,
                match_type="fallback_medium_text",
                reason="Средняя фраза без явной команды считается веб-поиском.",
                metadata={"source": "plugin_registry_fallback"},
            )

        return None

    def _match_exact(self, normalized_text: str, command: PluginCommand) -> PluginMatch | None:
        exact_phrases = _normalize_phrases(command.exact_phrases)

        for phrase in exact_phrases:
            if normalized_text == phrase:
                return PluginMatch(
                    plugin_id=command.plugin_id,
                    command_id=command.command_id,
                    intent=command.intent,
                    target_text="",
                    confidence=0.98,
                    match_type="exact",
                    matched_phrase=phrase,
                    reason=f"Точное совпадение с командой: {command.title}",
                    metadata=dict(command.metadata),
                )

        return None

    def _match_prefix(self, normalized_text: str, command: PluginCommand) -> PluginMatch | None:
        prefixes = _normalize_phrases(command.prefixes)

        for prefix in prefixes:
            if normalized_text == prefix:
                if command.requires_target:
                    logger.info(
                        "PluginRegistry prefix without target skipped | plugin=%s command=%s prefix=%s",
                        command.plugin_id,
                        command.command_id,
                        prefix,
                    )
                    return None

                return PluginMatch(
                    plugin_id=command.plugin_id,
                    command_id=command.command_id,
                    intent=command.intent,
                    target_text="",
                    confidence=0.88,
                    match_type="prefix_without_target",
                    matched_phrase=prefix,
                    reason=f"Совпадение с префиксом команды без цели: {command.title}",
                    metadata=dict(command.metadata),
                )

            if normalized_text.startswith(prefix + " "):
                target = normalized_text.replace(prefix, "", 1).strip()
                target = _cleanup_target(target, command.target_fillers)

                if command.requires_target and not target:
                    return None

                confidence = 0.90
                if len(prefix) >= 12:
                    confidence += 0.03
                if target:
                    confidence += 0.02

                return PluginMatch(
                    plugin_id=command.plugin_id,
                    command_id=command.command_id,
                    intent=command.intent,
                    target_text=target,
                    confidence=min(confidence, 0.96),
                    match_type="prefix",
                    matched_phrase=prefix,
                    reason=f"Совпадение по префиксу команды: {command.title}",
                    metadata=dict(command.metadata),
                )

        return None

    def _match_keyword(self, normalized_text: str, command: PluginCommand) -> PluginMatch | None:
        """
        Мягкое совпадение по ключевым словам.
        """
        keywords = _normalize_phrases(command.keywords)

        if not keywords:
            return None

        if command.requires_target and self.is_incomplete_command_text(normalized_text):
            logger.info(
                "PluginRegistry keyword skipped: incomplete command text | plugin=%s command=%s text=%s",
                command.plugin_id,
                command.command_id,
                normalized_text,
            )
            return None

        matched = []

        for keyword in keywords:
            if keyword and keyword in normalized_text:
                matched.append(keyword)

        if not matched:
            return None

        longest = max(matched, key=len)
        target = _cleanup_keyword_target(normalized_text, command, longest)

        if command.requires_target and not target:
            logger.info(
                "PluginRegistry keyword skipped: empty target after cleanup | plugin=%s command=%s text=%s",
                command.plugin_id,
                command.command_id,
                normalized_text,
            )
            return None

        return PluginMatch(
            plugin_id=command.plugin_id,
            command_id=command.command_id,
            intent=command.intent,
            target_text=target,
            confidence=0.52,
            match_type="keyword",
            matched_phrase=longest,
            reason=f"Мягкое совпадение по ключевому слову: {command.title}",
            metadata=dict(command.metadata),
        )

    def _get_command_priority(self, match: PluginMatch) -> int:
        for command in self.get_all_commands():
            if command.plugin_id == match.plugin_id and command.command_id == match.command_id:
                return command.priority

        return 0