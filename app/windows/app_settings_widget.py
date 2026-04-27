import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
    QCheckBox,
    QFormLayout,
)

from app.settings_service import settings_service
from app.logger import get_logger
from app.windows.ui_kit import make_page_title
from app.windows.floating_save_bar import FloatingSaveBar


logger = get_logger("app_settings_widget")


RUN_KEY_NAME = "LocalAssistant"


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
        self.layout.setSpacing(16)


class AppSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()

        logger.info("AppSettingsWidget | init_start")

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._loading_controls = False
        self._dirty = False
        self._saved_form_state = {}

        self._build_ui()
        self._connect_change_signals()
        self._load_from_settings(reset_dirty=True)

        logger.info("AppSettingsWidget | init_done")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = make_page_title("Настройки")
        header.addWidget(title, 0, 1)

        root.addLayout(header)

        card = InfoCard()

        description = QLabel(
            "Здесь находятся общие настройки запуска приложения и отображения служебных вкладок."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 18px; color: #4b5563;")
        card.layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        self.run_at_login_checkbox = QCheckBox("Запускать вместе с системой")
        self.run_at_login_checkbox.setToolTip(
            "Если включено, ассистент будет автоматически запускаться при входе в Windows."
        )

        self.hide_on_startup_checkbox = QCheckBox("Скрывать окно приложения при запуске")
        self.hide_on_startup_checkbox.setToolTip(
            "Если включено, при запуске будет открываться только значок в трее, "
            "а основное окно не будет показываться сразу."
        )

        self.show_system_tabs_checkbox = QCheckBox("Системные вкладки")
        self.show_system_tabs_checkbox.setToolTip(
            "Показывает дополнительные служебные вкладки: быстрые цели, папки, провайдеры, "
            "историю и пользовательские команды."
        )

        form.addRow("", self.run_at_login_checkbox)
        form.addRow("", self.hide_on_startup_checkbox)
        form.addRow("", self.show_system_tabs_checkbox)

        card.layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 15px; color: #687386;")
        card.layout.addWidget(self.status_label)

        root.addWidget(card)
        root.addStretch(1)

        self.save_bar = FloatingSaveBar(self, "Сохранить")
        self.save_bar.clicked.connect(self.save_settings)

    def _connect_change_signals(self):
        self.run_at_login_checkbox.stateChanged.connect(self._update_save_buttons)
        self.hide_on_startup_checkbox.stateChanged.connect(self._update_save_buttons)
        self.show_system_tabs_checkbox.stateChanged.connect(self._update_save_buttons)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_bar"):
            self.save_bar.reposition()

    def on_tab_activated(self):
        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def on_tab_deactivated(self):
        if self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot

        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _load_from_settings(self, reset_dirty: bool):
        self._loading_controls = True

        self.config = settings_service.get_all()

        startup = self.config.get("startup", {})
        ui = self.config.get("ui", {})

        self.run_at_login_checkbox.setChecked(
            bool(startup.get("run_at_login", False))
        )

        self.hide_on_startup_checkbox.setChecked(
            bool(startup.get("hide_window_on_startup", False))
        )

        self.show_system_tabs_checkbox.setChecked(
            bool(ui.get("show_system_tabs", False))
        )

        self._loading_controls = False

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self._set_save_buttons_enabled(self._dirty)

    def _capture_form_state(self) -> dict:
        return {
            "run_at_login": self.run_at_login_checkbox.isChecked(),
            "hide_window_on_startup": self.hide_on_startup_checkbox.isChecked(),
            "show_system_tabs": self.show_system_tabs_checkbox.isChecked(),
        }

    def _set_save_buttons_enabled(self, enabled: bool):
        self.save_bar.set_dirty(enabled)

    def _update_save_buttons(self):
        if self._loading_controls:
            return

        self._dirty = self._capture_form_state() != self._saved_form_state
        self._set_save_buttons_enabled(self._dirty)

    def _get_startup_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'

        project_root = Path(__file__).resolve().parents[2]
        assistant_app = project_root / "assistant_app.py"

        return f'"{sys.executable}" "{assistant_app}"'

    def _apply_windows_autostart(self, enabled: bool) -> tuple[bool, str]:
        if os.name != "nt":
            return False, "Автозапуск через реестр поддерживается только на Windows."

        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(
                        key,
                        RUN_KEY_NAME,
                        0,
                        winreg.REG_SZ,
                        self._get_startup_command(),
                    )
                else:
                    try:
                        winreg.DeleteValue(key, RUN_KEY_NAME)
                    except FileNotFoundError:
                        pass

            return True, ""

        except Exception as e:
            logger.exception("Не удалось изменить автозапуск: %s", e)
            return False, str(e)

    def save_settings(self):
        state = self._capture_form_state()

        autostart_ok, autostart_error = self._apply_windows_autostart(
            state["run_at_login"]
        )

        def mutator(cfg: dict):
            cfg.setdefault("startup", {})
            cfg.setdefault("ui", {})

            cfg["startup"]["run_at_login"] = state["run_at_login"]
            cfg["startup"]["hide_window_on_startup"] = state["hide_window_on_startup"]
            cfg["ui"]["show_system_tabs"] = state["show_system_tabs"]

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False
        self._set_save_buttons_enabled(False)

        if state["run_at_login"] and not autostart_ok:
            self.status_label.setText(
                f"Настройки сохранены, но автозапуск не удалось включить: {autostart_error}"
            )
            self.save_bar.show_saved("Сохранено!")
        else:
            self.status_label.setText("")
            self.save_bar.show_saved("Сохранено!")