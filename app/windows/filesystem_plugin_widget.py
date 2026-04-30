from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
)

from app.logger import get_logger
from app.plugins.resources import load_builtin_plugin_definitions
from app.settings_service import settings_service


logger = get_logger("filesystem_plugin_widget")


def _make_page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("font-size: 34px; font-weight: 600;")
    return label


def _make_status_badge() -> QLabel:
    label = QLabel("—")
    label.setAlignment(Qt.AlignCenter)
    label.setMinimumWidth(170)
    return label


def _apply_status_style(label: QLabel, status_kind: str):
    if status_kind == "ok":
        bg, fg = "#e7f6ec", "#16723a"
    elif status_kind == "process":
        bg, fg = "#fff3d6", "#8a5a00"
    else:
        bg, fg = "#fde8e8", "#9b1c1c"

    label.setStyleSheet(f"""
        QLabel {{
            font-size: 21px;
            font-weight: 700;
            padding: 8px 16px;
            border-radius: 12px;
            background: {bg};
            color: {fg};
        }}
    """)


class InfoCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("InfoCard")
        self.setStyleSheet("""
            QFrame#InfoCard {
                background: #ffffff;
                border: 1px solid #dde2ea;
                border-radius: 14px;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(14)


class FilesystemPluginWidget(QWidget):
    """
    Plugin-tab для filesystem plugin.

    Показывает:
    - включён ли плагин;
    - что он делает;
    - какие команды объявлены в plugin resources.
    """

    def __init__(self):
        super().__init__()

        logger.info("FilesystemPluginWidget | init_start")

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._build_ui()
        self._load_commands_from_resources()
        self.refresh_all()

        logger.info("FilesystemPluginWidget | init_done")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = _make_page_title("Файловая система")
        self.status_badge = _make_status_badge()

        header.addWidget(title, 0, 1)
        header.addWidget(
            self.status_badge,
            0,
            2,
            alignment=Qt.AlignRight | Qt.AlignVCenter,
        )

        root.addLayout(header)

        overview_card = InfoCard()

        description = QLabel(
            "Эта вкладка относится к filesystem plugin. "
            "Он отвечает за открытие приложений, файлов и папок через локальный индекс и resolver."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 17px; color: #4b5563;")
        overview_card.layout.addWidget(description)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        plugin_status_caption = QLabel("Плагин:")
        plugin_status_caption.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.plugin_status_value = QLabel("—")
        self.plugin_status_value.setStyleSheet("font-size: 18px;")

        role_caption = QLabel("Роль:")
        role_caption.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.role_value = QLabel("Открытие приложений, файлов и папок")
        self.role_value.setStyleSheet("font-size: 18px;")

        grid.addWidget(plugin_status_caption, 0, 0)
        grid.addWidget(self.plugin_status_value, 0, 1)
        grid.addWidget(role_caption, 1, 0)
        grid.addWidget(self.role_value, 1, 1)

        overview_card.layout.addLayout(grid)

        self.runtime_hint = QLabel("")
        self.runtime_hint.setWordWrap(True)
        self.runtime_hint.setStyleSheet("font-size: 15px; color: #687386;")
        overview_card.layout.addWidget(self.runtime_hint)

        root.addWidget(overview_card)

        commands_card = InfoCard()

        commands_title = QLabel("Команды filesystem plugin")
        commands_title.setStyleSheet("font-size: 24px; font-weight: 600; color: #111827;")
        commands_card.layout.addWidget(commands_title)

        commands_description = QLabel(
            "Список ниже берётся из plugin resources. "
            "Это те команды, которые parser и registry связывают с filesystem plugin."
        )
        commands_description.setWordWrap(True)
        commands_description.setStyleSheet("font-size: 16px; color: #4b5563;")
        commands_card.layout.addWidget(commands_description)

        self.open_file_label = QLabel("—")
        self.open_file_label.setWordWrap(True)
        self.open_file_label.setStyleSheet("font-size: 16px;")

        self.open_folder_label = QLabel("—")
        self.open_folder_label.setWordWrap(True)
        self.open_folder_label.setStyleSheet("font-size: 16px;")

        self.open_anything_label = QLabel("—")
        self.open_anything_label.setWordWrap(True)
        self.open_anything_label.setStyleSheet("font-size: 16px;")

        commands_card.layout.addWidget(self.open_file_label)
        commands_card.layout.addWidget(self.open_folder_label)
        commands_card.layout.addWidget(self.open_anything_label)

        root.addWidget(commands_card)
        root.addStretch(1)

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot
        self.refresh_all()

    def _is_plugin_enabled(self) -> bool:
        plugins_cfg = self.config.get("plugins", {})
        enabled_map = plugins_cfg.get("enabled")

        if isinstance(enabled_map, dict):
            return bool(enabled_map.get("filesystem", True))

        legacy_enabled = self.config.get("assistant", {}).get("enabled_plugins")
        if isinstance(legacy_enabled, list):
            return "filesystem" in {str(item) for item in legacy_enabled}

        return True

    def _load_commands_from_resources(self):
        definitions = load_builtin_plugin_definitions()

        filesystem_definition = None
        for definition in definitions:
            if definition.plugin_id == "filesystem":
                filesystem_definition = definition
                break

        if filesystem_definition is None:
            self.open_file_label.setText("Команды filesystem plugin не найдены.")
            self.open_folder_label.setText("")
            self.open_anything_label.setText("")
            return

        command_map = {command.command_id: command for command in filesystem_definition.commands}

        self.open_file_label.setText(self._command_preview(command_map.get("open_file"), "Открыть файл"))
        self.open_folder_label.setText(self._command_preview(command_map.get("open_folder"), "Открыть папку"))
        self.open_anything_label.setText(self._command_preview(command_map.get("open_anything"), "Открыть приложение / объект"))

    def _command_preview(self, command, title: str) -> str:
        if command is None:
            return f"<b>{title}:</b> команда не найдена"

        phrases = command.exact_phrases or command.prefixes or []
        preview = ", ".join(phrases[:6]) if phrases else "Фразы не заданы"
        return f"<b>{title}:</b> {preview}"

    def refresh_all(self):
        enabled = self._is_plugin_enabled()

        if enabled:
            self.plugin_status_value.setText("включён")
            self.status_badge.setText("Активен")
            _apply_status_style(self.status_badge, "ok")
            self.runtime_hint.setText(
                "Плагин включён. Команды открытия приложений, файлов и папок будут участвовать в обычном parser/plugin flow."
            )
        else:
            self.plugin_status_value.setText("выключен")
            self.status_badge.setText("Выключен")
            _apply_status_style(self.status_badge, "bad")
            self.runtime_hint.setText(
                "Плагин выключен. Команды открытия приложений, файлов и папок больше не будут матчиться parser-ом."
            )

    def on_tab_activated(self):
        self.refresh_all()

    def on_tab_deactivated(self):
        pass