from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
    QPushButton,
)

from app.chat.state import chat_state
from app.logger import get_logger
from app.plugins.resources import load_builtin_plugin_definitions
from app.settings_service import settings_service


logger = get_logger("chat_plugin_widget")


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


class ChatPluginWidget(QWidget):
    """
    Первая реальная plugin-tab.

    Задачи вкладки:
    - показать, что chat plugin реально подключается как отдельная вкладка;
    - показать runtime-состояние chat mode;
    - дать простой UI для ручного включения/выключения режима общения;
    - отобразить команды плагина из plugin resources.
    """

    def __init__(self):
        super().__init__()

        logger.info("ChatPluginWidget | init_start")

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(700)
        self._poll_timer.timeout.connect(self.refresh_runtime_state)

        self._build_ui()
        self._load_commands_from_resources()
        self.refresh_all()

        logger.info("ChatPluginWidget | init_done")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = _make_page_title("Общение")
        self.runtime_status_badge = _make_status_badge()

        header.addWidget(title, 0, 1)
        header.addWidget(
            self.runtime_status_badge,
            0,
            2,
            alignment=Qt.AlignRight | Qt.AlignVCenter,
        )

        root.addLayout(header)

        overview_card = InfoCard()

        description = QLabel(
            "Эта вкладка относится к chat plugin. Здесь можно посмотреть его состояние, "
            "вручную включить или выключить режим общения и увидеть команды, "
            "которые объявлены в plugin resources."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 17px; color: #4b5563;")
        overview_card.layout.addWidget(description)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(16)
        status_grid.setVerticalSpacing(10)

        plugin_status_caption = QLabel("Плагин:")
        plugin_status_caption.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.plugin_status_value = QLabel("—")
        self.plugin_status_value.setStyleSheet("font-size: 18px;")

        mode_status_caption = QLabel("Режим общения:")
        mode_status_caption.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.mode_status_value = QLabel("—")
        self.mode_status_value.setStyleSheet("font-size: 18px;")

        status_grid.addWidget(plugin_status_caption, 0, 0)
        status_grid.addWidget(self.plugin_status_value, 0, 1)
        status_grid.addWidget(mode_status_caption, 1, 0)
        status_grid.addWidget(self.mode_status_value, 1, 1)

        overview_card.layout.addLayout(status_grid)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)

        self.enable_btn = QPushButton("Включить режим общения")
        self.enable_btn.clicked.connect(self.enable_chat_mode)

        self.disable_btn = QPushButton("Выключить режим общения")
        self.disable_btn.clicked.connect(self.disable_chat_mode)

        buttons_row.addWidget(self.enable_btn)
        buttons_row.addWidget(self.disable_btn)
        buttons_row.addStretch(1)

        overview_card.layout.addLayout(buttons_row)

        self.runtime_hint = QLabel("")
        self.runtime_hint.setWordWrap(True)
        self.runtime_hint.setStyleSheet("font-size: 15px; color: #687386;")
        overview_card.layout.addWidget(self.runtime_hint)

        root.addWidget(overview_card)

        commands_card = InfoCard()

        commands_title = QLabel("Команды chat plugin")
        commands_title.setStyleSheet("font-size: 24px; font-weight: 600; color: #111827;")
        commands_card.layout.addWidget(commands_title)

        commands_description = QLabel(
            "Список ниже берётся из plugin resources, а не из отдельного захардкоженного списка внутри UI."
        )
        commands_description.setWordWrap(True)
        commands_description.setStyleSheet("font-size: 16px; color: #4b5563;")
        commands_card.layout.addWidget(commands_description)

        self.enable_command_label = QLabel("—")
        self.enable_command_label.setWordWrap(True)
        self.enable_command_label.setStyleSheet("font-size: 16px;")

        self.disable_command_label = QLabel("—")
        self.disable_command_label.setWordWrap(True)
        self.disable_command_label.setStyleSheet("font-size: 16px;")

        commands_card.layout.addWidget(self.enable_command_label)
        commands_card.layout.addWidget(self.disable_command_label)

        root.addWidget(commands_card)
        root.addStretch(1)

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot
        self.refresh_all()

    def _is_chat_plugin_enabled(self) -> bool:
        plugins_cfg = self.config.get("plugins", {})
        enabled_map = plugins_cfg.get("enabled")

        if isinstance(enabled_map, dict):
            return bool(enabled_map.get("chat", True))

        legacy_enabled = self.config.get("assistant", {}).get("enabled_plugins")
        if isinstance(legacy_enabled, list):
            return "chat" in {str(item) for item in legacy_enabled}

        return True

    def _load_commands_from_resources(self):
        definitions = load_builtin_plugin_definitions()

        chat_definition = None
        for definition in definitions:
            if definition.plugin_id == "chat":
                chat_definition = definition
                break

        if chat_definition is None:
            self.enable_command_label.setText("Команда включения не найдена.")
            self.disable_command_label.setText("Команда выключения не найдена.")
            return

        enable_command = None
        disable_command = None

        for command in chat_definition.commands:
            if command.command_id == "enable_chat_mode":
                enable_command = command
            elif command.command_id == "disable_chat_mode":
                disable_command = command

        if enable_command is not None:
            phrases = enable_command.exact_phrases or enable_command.prefixes or []
            preview = ", ".join(phrases[:6]) if phrases else "Фразы не заданы"
            self.enable_command_label.setText(
                f"<b>Включение:</b> {preview}"
            )
        else:
            self.enable_command_label.setText("Команда включения не найдена.")

        if disable_command is not None:
            phrases = disable_command.exact_phrases or disable_command.prefixes or []
            preview = ", ".join(phrases[:6]) if phrases else "Фразы не заданы"
            self.disable_command_label.setText(
                f"<b>Выключение:</b> {preview}"
            )
        else:
            self.disable_command_label.setText("Команда выключения не найдена.")

    def refresh_runtime_state(self):
        plugin_enabled = self._is_chat_plugin_enabled()
        mode_enabled = chat_state.is_enabled()

        if plugin_enabled:
            self.plugin_status_value.setText("включён")
        else:
            self.plugin_status_value.setText("выключен")

        if mode_enabled:
            self.mode_status_value.setText("активен")
            self.runtime_status_badge.setText("Активно")
            _apply_status_style(self.runtime_status_badge, "ok")
        else:
            self.mode_status_value.setText("не активен")
            self.runtime_status_badge.setText("Выключено")
            _apply_status_style(self.runtime_status_badge, "bad")

        self.enable_btn.setEnabled(plugin_enabled and not mode_enabled)
        self.disable_btn.setEnabled(plugin_enabled and mode_enabled)

        if not plugin_enabled:
            self.runtime_hint.setText(
                "Chat plugin выключен в настройках ассистента, поэтому режим общения сейчас недоступен."
            )
        elif mode_enabled:
            self.runtime_hint.setText(
                "Режим общения уже активен. Следующая голосовая команда будет обработана как сообщение для ИИ, пока режим не будет выключен."
            )
        else:
            self.runtime_hint.setText(
                "Режим общения сейчас выключен. Его можно включить голосовой командой или кнопкой на этой вкладке."
            )

    def refresh_all(self):
        self.refresh_runtime_state()

    def enable_chat_mode(self):
        if not self._is_chat_plugin_enabled():
            return

        chat_state.enable()
        logger.info("ChatPluginWidget | chat mode enabled from UI")
        self.refresh_runtime_state()

    def disable_chat_mode(self):
        if not self._is_chat_plugin_enabled():
            return

        chat_state.disable()
        logger.info("ChatPluginWidget | chat mode disabled from UI")
        self.refresh_runtime_state()

    def on_tab_activated(self):
        self.refresh_all()
        if not self._poll_timer.isActive():
            self._poll_timer.start()

    def on_tab_deactivated(self):
        self._poll_timer.stop()