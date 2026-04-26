from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGridLayout,
    QFormLayout,
    QCheckBox,
)

from app.settings_service import settings_service
from app.windows.floating_save_bar import FloatingSaveBar
from app.windows.startup_manager import is_startup_enabled, set_startup_enabled
from app.windows.ui_kit import make_page_title, InfoCard


class AppSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._loading = False
        self._dirty = False
        self._saved_form_state = {}

        self._build_ui()
        self._connect_signals()
        self._load_from_settings(reset_dirty=True)

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
            "Здесь находятся общие настройки запуска, поведения окна и отображения технических разделов."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 18px; color: #303846;")
        card.layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        self.run_with_system_checkbox = QCheckBox("Запускать вместе с системой")
        self.run_with_system_checkbox.setToolTip(
            "Если включено, Windows будет запускать LocalAssistant автоматически после входа в систему."
        )

        self.hide_on_startup_checkbox = QCheckBox("Скрывать окно приложения при запуске")
        self.hide_on_startup_checkbox.setToolTip(
            "Если включено, при запуске ассистент будет сразу работать в фоне, а окно не будет открываться."
        )

        self.system_tabs_checkbox = QCheckBox("Системные вкладки")
        self.system_tabs_checkbox.setToolTip(
            "Показывает дополнительные технические вкладки: быстрые цели, папки, провайдеры, историю и пользовательские команды."
        )

        form.addRow("", self.run_with_system_checkbox)
        form.addRow("", self.hide_on_startup_checkbox)
        form.addRow("", self.system_tabs_checkbox)

        card.layout.addLayout(form)
        root.addWidget(card)
        root.addStretch(1)

        self.save_bar = FloatingSaveBar(self, "Сохранить")
        self.save_bar.clicked.connect(self.save_settings)

    def _connect_signals(self):
        self.run_with_system_checkbox.stateChanged.connect(self._update_dirty)
        self.hide_on_startup_checkbox.stateChanged.connect(self._update_dirty)
        self.system_tabs_checkbox.stateChanged.connect(self._update_dirty)

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
        self._loading = True

        self.config = settings_service.get_all()
        ui = self.config.get("ui", {})
        startup = self.config.get("startup", {})

        saved_startup_enabled = bool(startup.get("run_with_system", False))
        real_startup_enabled = is_startup_enabled()

        self.run_with_system_checkbox.setChecked(saved_startup_enabled or real_startup_enabled)
        self.hide_on_startup_checkbox.setChecked(bool(ui.get("hide_window_on_startup", False)))
        self.system_tabs_checkbox.setChecked(bool(ui.get("show_system_tabs", False)))

        self._loading = False

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self.save_bar.set_dirty(self._dirty)

    def _capture_form_state(self) -> dict:
        return {
            "run_with_system": self.run_with_system_checkbox.isChecked(),
            "hide_window_on_startup": self.hide_on_startup_checkbox.isChecked(),
            "show_system_tabs": self.system_tabs_checkbox.isChecked(),
        }

    def _update_dirty(self):
        if self._loading:
            return

        self._dirty = self._capture_form_state() != self._saved_form_state
        self.save_bar.set_dirty(self._dirty)

    def save_settings(self):
        state = self._capture_form_state()

        set_startup_enabled(state["run_with_system"])

        def mutator(cfg: dict):
            cfg.setdefault("startup", {})
            cfg.setdefault("ui", {})

            cfg["startup"]["run_with_system"] = state["run_with_system"]
            cfg["ui"]["hide_window_on_startup"] = state["hide_window_on_startup"]
            cfg["ui"]["show_system_tabs"] = state["show_system_tabs"]

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False

        self.save_bar.show_saved("Сохранено!")