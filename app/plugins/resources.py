import json
from importlib import resources

from app.logger import get_logger
from app.plugins.defaults import BUILTIN_PLUGIN_ORDER, DEFAULT_PLUGIN_ENABLED
from app.plugins.models import PluginCommand, PluginDefinition


logger = get_logger("plugin_resources")


RESOURCE_PACKAGE = "app.plugins.builtin"
COMMANDS_RESOURCE_FILE = "commands.json"


def _as_list(value) -> list[str]:
    """
    Безопасно приводит значение из JSON к списку строк.
    """
    if not value:
        return []

    if not isinstance(value, list):
        return []

    result = []
    for item in value:
        item = str(item).strip()
        if item:
            result.append(item)

    return result


def _as_dict(value) -> dict:
    """
    Безопасно приводит значение из JSON к словарю.
    """
    if isinstance(value, dict):
        return dict(value)

    return {}


def _command_from_dict(plugin_id: str, data: dict) -> PluginCommand:
    """
    Создаёт PluginCommand из JSON-описания.
    """
    command_id = str(data.get("command_id", "")).strip()
    intent = str(data.get("intent", "")).strip()
    title = str(data.get("title", command_id)).strip()

    if not command_id:
        raise ValueError(f"У команды плагина {plugin_id!r} не указан command_id")

    if not intent:
        raise ValueError(f"У команды {plugin_id}.{command_id} не указан intent")

    return PluginCommand(
        plugin_id=plugin_id,
        command_id=command_id,
        intent=intent,
        title=title or command_id,
        exact_phrases=_as_list(data.get("exact_phrases")),
        prefixes=_as_list(data.get("prefixes")),
        keywords=_as_list(data.get("keywords")),
        target_fillers=_as_list(data.get("target_fillers")),
        requires_target=bool(data.get("requires_target", True)),
        priority=int(data.get("priority", 50)),
        metadata=_as_dict(data.get("metadata")),
    )


def _definition_from_dict(data: dict) -> PluginDefinition:
    """
    Создаёт PluginDefinition из JSON-описания.
    """
    plugin_id = str(data.get("plugin_id", "")).strip()

    if not plugin_id:
        raise ValueError("В описании плагина не указан plugin_id")

    commands = []
    for command_data in data.get("commands", []):
        if not isinstance(command_data, dict):
            continue

        commands.append(_command_from_dict(plugin_id, command_data))

    return PluginDefinition(
        plugin_id=plugin_id,
        title=str(data.get("title", plugin_id)).strip() or plugin_id,
        description=str(data.get("description", "")).strip(),
        default_enabled=bool(
            data.get(
                "default_enabled",
                DEFAULT_PLUGIN_ENABLED.get(plugin_id, True),
            )
        ),
        commands=commands,
    )


def _sort_definitions(definitions: list[PluginDefinition]) -> list[PluginDefinition]:
    """
    Сортирует плагины в стабильном порядке.
    """
    order_map = {
        plugin_id: index
        for index, plugin_id in enumerate(BUILTIN_PLUGIN_ORDER)
    }

    return sorted(
        definitions,
        key=lambda item: order_map.get(item.plugin_id, 999),
    )


def _fallback_builtin_plugin_definitions() -> list[PluginDefinition]:
    """
    Минимальный fallback на случай, если JSON-ресурс не был найден.

    Это страховка для разработки и будущей сборки PyInstaller.
    Основной источник команд — app/plugins/builtin/commands.json.
    """
    logger.warning("Используется минимальный fallback описаний встроенных плагинов.")

    data = {
        "plugins": [
            {
                "plugin_id": "filesystem",
                "title": "Файловая система",
                "description": "Открытие приложений, файлов и папок.",
                "default_enabled": True,
                "commands": [
                    {
                        "command_id": "open_anything",
                        "intent": "generic_open",
                        "title": "Открыть приложение, файл или папку",
                        "prefixes": ["открой", "запусти", "покажи"],
                        "target_fillers": ["приложение", "программа"],
                        "requires_target": True,
                        "priority": 65
                    }
                ]
            },
            {
                "plugin_id": "web",
                "title": "Веб",
                "description": "Поиск в интернете.",
                "default_enabled": True,
                "commands": [
                    {
                        "command_id": "search_web",
                        "intent": "search_web",
                        "title": "Поиск в интернете",
                        "prefixes": ["найди в интернете", "загугли"],
                        "keywords": ["интернет", "гугл", "google"],
                        "requires_target": True,
                        "priority": 82
                    }
                ]
            },
            {
                "plugin_id": "music",
                "title": "Музыка",
                "description": "Поиск музыки.",
                "default_enabled": True,
                "commands": [
                    {
                        "command_id": "play_music_query",
                        "intent": "play_music_query",
                        "title": "Найти или включить музыку",
                        "prefixes": ["включи музыку", "включи песню"],
                        "keywords": ["музыка", "музыку", "песня", "трек"],
                        "requires_target": True,
                        "priority": 90
                    }
                ]
            },
            {
                "plugin_id": "dictation",
                "title": "Диктовка",
                "description": "Режим диктовки.",
                "default_enabled": True,
                "commands": [
                    {
                        "command_id": "enable_dictation",
                        "intent": "enable_dictation",
                        "title": "Включить диктовку",
                        "exact_phrases": ["включи диктовку", "включи режим диктовки"],
                        "requires_target": False,
                        "priority": 95
                    },
                    {
                        "command_id": "disable_dictation",
                        "intent": "disable_dictation",
                        "title": "Выключить диктовку",
                        "exact_phrases": ["выключи диктовку", "выключи режим диктовки"],
                        "requires_target": False,
                        "priority": 95
                    }
                ]
            },
            {
                "plugin_id": "chat",
                "title": "Общение",
                "description": "Режим общения с ИИ.",
                "default_enabled": True,
                "commands": [
                    {
                        "command_id": "enable_chat_mode",
                        "intent": "enable_chat_mode",
                        "title": "Включить режим общения",
                        "exact_phrases": ["включи режим общения", "давай поговорим"],
                        "requires_target": False,
                        "priority": 95
                    },
                    {
                        "command_id": "disable_chat_mode",
                        "intent": "disable_chat_mode",
                        "title": "Выключить режим общения",
                        "exact_phrases": ["выключи режим общения", "заверши общение"],
                        "requires_target": False,
                        "priority": 95
                    }
                ]
            }
        ]
    }

    definitions = [
        _definition_from_dict(plugin_data)
        for plugin_data in data.get("plugins", [])
        if isinstance(plugin_data, dict)
    ]

    return _sort_definitions(definitions)


def load_builtin_plugin_definitions() -> list[PluginDefinition]:
    """
    Загружает описания встроенных плагинов из JSON-ресурса.
    """
    try:
        resource_path = resources.files(RESOURCE_PACKAGE).joinpath(COMMANDS_RESOURCE_FILE)
        raw_text = resource_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)

        definitions = [
            _definition_from_dict(plugin_data)
            for plugin_data in data.get("plugins", [])
            if isinstance(plugin_data, dict)
        ]

        if not definitions:
            raise ValueError("JSON встроенных плагинов не содержит ни одного плагина.")

        logger.info(
            "Описания встроенных плагинов загружены из JSON: plugins=%s",
            [item.plugin_id for item in definitions],
        )

        return _sort_definitions(definitions)

    except Exception as e:
        logger.exception("Не удалось загрузить JSON встроенных плагинов: %s", e)
        return _fallback_builtin_plugin_definitions()