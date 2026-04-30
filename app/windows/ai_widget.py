from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QFrame,
    QToolButton,
)

from app.settings_service import settings_service
from app.ai.ollama_model_discovery import list_available_ollama_models
from app.ai.ollama_health import quick_server_check, check_ollama_model
from app.logger import get_logger
from app.windows.floating_save_bar import FloatingSaveBar


logger = get_logger("ai_widget")


LOCAL_PROVIDER_OPTIONS = [
    ("stub", "Без модели / заглушка"),
    ("ollama", "Ollama"),
]

REMOTE_PROVIDER_OPTIONS = [
    ("openai_compatible", "OpenAI-compatible API"),
    ("openai", "OpenAI"),
    ("deepseek", "DeepSeek"),
    ("yandexgpt", "YandexGPT"),
]

SUPPORTED_RUNTIME_PROVIDERS = {"stub", "ollama"}

DEFAULT_ENDPOINTS = {
    "stub": "",
    "ollama": "http://localhost:11434",
    "openai_compatible": "",
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "yandexgpt": "https://llm.api.cloud.yandex.net",
}


class OllamaCheckWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, mode: str, host: str, model: str):
        super().__init__()
        self.mode = mode
        self.host = host
        self.model = model

    def run(self):
        try:
            if self.mode == "server":
                ok, message = quick_server_check(self.host)
            else:
                ok, message = check_ollama_model(self.host, self.model)

            self.finished.emit(ok, message)
        except Exception as e:
            self.finished.emit(False, f"Ошибка проверки Ollama: {e}")


class OllamaModelsLoadWorker(QObject):
    finished = Signal(list, str)

    def __init__(self, models_path: str):
        super().__init__()
        self.models_path = models_path

    def run(self):
        try:
            models = list_available_ollama_models(self.models_path)
            self.finished.emit(models, "")
        except Exception as e:
            self.finished.emit([], str(e))


def _make_page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("font-size: 34px; font-weight: 600;")
    return label


def _make_status_badge() -> QLabel:
    label = QLabel("XXX")
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
            font-size: 25px;
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


def _make_row_widget(layout: QHBoxLayout) -> QWidget:
    widget = QWidget()
    widget.setLayout(layout)
    return widget


class AISettingsWidget(QWidget):
    def __init__(self):
        super().__init__()

        logger.info("AISettingsWidget | init_start")

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._check_thread = None
        self._check_worker = None

        self._models_thread = None
        self._models_worker = None

        self._loading_controls = False
        self._dirty = False
        self._saved_form_state = {}

        self._check_in_progress = False
        self.last_model_check_ok = None
        self.last_model_check_message = ""

        self._build_ui()
        self._connect_change_signals()
        self._load_from_settings(reset_dirty=True)

        logger.info("AISettingsWidget | init_done")

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot

        if not self._dirty:
            self._load_from_settings(reset_dirty=True)
        else:
            self.refresh_status()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = _make_page_title("Искусственный\nинтеллект")
        self.overall_status = _make_status_badge()

        header.addWidget(title, 0, 1)
        header.addWidget(
            self.overall_status,
            0,
            2,
            alignment=Qt.AlignRight | Qt.AlignVCenter,
        )

        root.addLayout(header)

        card = InfoCard()

        self.model_label = QLabel()
        self.model_label.setStyleSheet("font-size: 24px; font-weight: 500;")
        self.model_label.setToolTip(
            "Здесь показывается только доступность модели. Конкретный провайдер, адрес API и название модели находятся в расширенных настройках."
        )

        self.apply_to_all_checkbox = QCheckBox("Включить ассистенту интеллект на всё")
        self.apply_to_all_checkbox.setToolTip(
            "Если включено, после распознавания речи команда дополнительно передаётся ИИ "
            "для очистки и уточнения. Если выключено, ассистент работает только по обычным правилам."
        )

        main_row = QHBoxLayout()
        main_row.addWidget(self.apply_to_all_checkbox)
        main_row.addStretch(1)

        card.layout.addWidget(self.model_label)
        card.layout.addLayout(main_row)

        root.addWidget(card)

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Расширенные настройки")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setArrowType(Qt.RightArrow)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_toggle.setStyleSheet("""
            QToolButton {
                font-size: 24px;
                font-weight: 500;
                border: none;
                padding: 10px 0;
            }
        """)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)

        root.addWidget(self.advanced_toggle)

        self.advanced_panel = QFrame()
        self.advanced_panel.setObjectName("AdvancedPanel")
        self.advanced_panel.setVisible(False)
        self.advanced_panel.setStyleSheet("""
            QFrame#AdvancedPanel {
                background: #ffffff;
                border: 1px solid #dde2ea;
                border-radius: 14px;
            }
        """)

        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(24, 20, 24, 20)
        advanced_layout.setSpacing(14)

        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.setFormAlignment(Qt.AlignTop)

        self.enabled_checkbox = QCheckBox("Включить ИИ-режим")
        self.enabled_checkbox.setToolTip(
            "Полностью включает или выключает ИИ-слой ассистента."
        )

        self.location_label = QLabel("Расположение:")
        self.location_combo = QComboBox()
        self.location_combo.addItem("Локально", "local")
        self.location_combo.addItem("Удалённо", "remote")
        self.location_combo.setToolTip(
            "Локальная модель работает на компьютере пользователя. Удалённая модель вызывается через API."
        )

        self.provider_label = QLabel("Провайдер:")
        self.provider_combo = QComboBox()
        self.provider_combo.setToolTip(
            "Провайдер определяет, через какой интерфейс ассистент будет обращаться к языковой модели."
        )

        self.provider_endpoint_label = QLabel("Адрес сервера / API:")
        self.provider_endpoint_edit = QLineEdit()
        self.provider_endpoint_edit.setPlaceholderText("Например: http://localhost:11434 или https://api.example.com/v1")
        self.provider_endpoint_edit.setToolTip(
            "Для Ollama это локальный адрес сервера. Для удалённых провайдеров — адрес API."
        )

        self.api_key_label = QLabel("API-ключ:")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Нужен для удалённых провайдеров.")
        self.api_key_edit.setToolTip(
            "Ключ доступа к удалённому API. Для локальной Ollama обычно не нужен."
        )

        self.command_model_label = QLabel("Модель для команд:")
        self.command_model_combo = QComboBox()
        self.command_model_combo.setEditable(True)
        self.command_model_combo.setInsertPolicy(QComboBox.NoInsert)
        self.command_model_combo.setToolTip(
            "Модель, которая используется для уточнения и нормализации команд после распознавания речи."
        )

        self.chat_model_label = QLabel("Модель для общения:")
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.setEditable(True)
        self.chat_model_combo.setInsertPolicy(QComboBox.NoInsert)
        self.chat_model_combo.setToolTip(
            "Модель, которая будет использоваться для режима общения. Если не выбрана, может использоваться основная модель."
        )

        self.refresh_models_btn = QPushButton("Обновить список моделей")
        self.refresh_models_btn.clicked.connect(self.load_models)
        self.refresh_models_btn.setToolTip(
            "Автоматическое обновление списка моделей сейчас доступно только для локальной Ollama."
        )

        command_model_row = QHBoxLayout()
        command_model_row.addWidget(self.command_model_combo)
        command_model_row.addWidget(self.refresh_models_btn)
        self.command_model_row_widget = _make_row_widget(command_model_row)

        chat_model_row = QHBoxLayout()
        chat_model_row.addWidget(self.chat_model_combo)
        self.chat_model_row_widget = _make_row_widget(chat_model_row)

        self.ollama_models_path_label = QLabel("Путь к моделям Ollama:")
        self.ollama_models_path_edit = QLineEdit()
        self.ollama_models_path_edit.setPlaceholderText("Необязательно. Используется только для локального поиска моделей Ollama.")
        self.ollama_models_path_edit.setToolTip(
            "Дополнительный путь для поиска локальных моделей Ollama. Обычно можно оставить пустым."
        )

        self.speak_checkbox = QCheckBox("Озвучивать ответы")
        self.speak_checkbox.setToolTip(
            "Если включено, ответы режима общения будут озвучиваться голосом ассистента."
        )

        self.future_provider_hint = QLabel()
        self.future_provider_hint.setWordWrap(True)
        self.future_provider_hint.setStyleSheet("font-size: 14px; color: #687386;")

        self.form.addRow("", self.enabled_checkbox)
        self.form.addRow(self.location_label, self.location_combo)
        self.form.addRow(self.provider_label, self.provider_combo)
        self.form.addRow(self.provider_endpoint_label, self.provider_endpoint_edit)
        self.form.addRow(self.api_key_label, self.api_key_edit)
        self.form.addRow(self.command_model_label, self.command_model_row_widget)
        self.form.addRow(self.chat_model_label, self.chat_model_row_widget)
        self.form.addRow(self.ollama_models_path_label, self.ollama_models_path_edit)
        self.form.addRow("", self.speak_checkbox)

        advanced_layout.addLayout(self.form)
        advanced_layout.addWidget(self.future_provider_hint)

        self.check_status_label = QLabel("")
        self.check_status_label.setWordWrap(True)
        self.check_status_label.setStyleSheet("font-size: 15px; color: #555;")
        advanced_layout.addWidget(self.check_status_label)

        buttons_row = QHBoxLayout()

        self.check_server_btn = QPushButton("Проверить сервер")
        self.check_server_btn.clicked.connect(self.check_server)

        self.check_model_btn = QPushButton("Проверить модель")
        self.check_model_btn.clicked.connect(self.check_model)

        buttons_row.addWidget(self.check_server_btn)
        buttons_row.addWidget(self.check_model_btn)
        buttons_row.addStretch(1)

        advanced_layout.addLayout(buttons_row)

        root.addWidget(self.advanced_panel)
        root.addStretch(1)

        self.save_bar = FloatingSaveBar(self, "Сохранить")
        self.save_bar.clicked.connect(self.save_settings)

    def _connect_change_signals(self):
        self.apply_to_all_checkbox.stateChanged.connect(self._update_save_buttons)
        self.enabled_checkbox.stateChanged.connect(self._update_save_buttons)
        self.location_combo.currentIndexChanged.connect(self._on_location_changed)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self.provider_endpoint_edit.textChanged.connect(self._update_save_buttons)
        self.api_key_edit.textChanged.connect(self._update_save_buttons)
        self.command_model_combo.currentTextChanged.connect(self._update_save_buttons)
        self.chat_model_combo.currentTextChanged.connect(self._update_save_buttons)
        self.ollama_models_path_edit.textChanged.connect(self._update_save_buttons)
        self.speak_checkbox.stateChanged.connect(self._update_save_buttons)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_bar"):
            self.save_bar.reposition()

    def _toggle_advanced(self, checked: bool):
        self.advanced_panel.setVisible(checked)
        self.advanced_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.save_bar.reposition()

    def on_tab_activated(self):
        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def on_tab_deactivated(self):
        if self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _location_key(self) -> str:
        return self.location_combo.currentData() or "local"

    def _provider_key(self) -> str:
        return self.provider_combo.currentData() or "stub"

    def _provider_options_for_location(self, location: str) -> list[tuple[str, str]]:
        if location == "remote":
            return REMOTE_PROVIDER_OPTIONS
        return LOCAL_PROVIDER_OPTIONS

    def _set_location_key(self, key: str):
        for i in range(self.location_combo.count()):
            if self.location_combo.itemData(i) == key:
                self.location_combo.setCurrentIndex(i)
                return
        self.location_combo.setCurrentIndex(0)

    def _populate_provider_combo(self, location: str, selected_provider: str | None = None):
        options = self._provider_options_for_location(location)

        self.provider_combo.clear()
        for key, label in options:
            self.provider_combo.addItem(label, key)

        selected_provider = selected_provider or ""

        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == selected_provider:
                self.provider_combo.setCurrentIndex(i)
                return

        if self.provider_combo.count() > 0:
            self.provider_combo.setCurrentIndex(0)

    def _set_row_visible(self, label: QLabel, widget: QWidget, visible: bool):
        label.setVisible(visible)
        widget.setVisible(visible)

    def _on_location_changed(self):
        if self._loading_controls:
            return

        location = self._location_key()
        self._populate_provider_combo(location)

        provider = self._provider_key()
        default_endpoint = DEFAULT_ENDPOINTS.get(provider, "")
        self.provider_endpoint_edit.setText(default_endpoint)

        self._update_provider_controls()
        self._update_save_buttons()

    def _on_provider_changed(self):
        if self._loading_controls:
            return

        provider = self._provider_key()

        default_endpoint = DEFAULT_ENDPOINTS.get(provider, "")
        current_endpoint = self.provider_endpoint_edit.text().strip()

        if not current_endpoint or provider in {"stub", "ollama", "openai", "deepseek", "yandexgpt"}:
            self.provider_endpoint_edit.setText(default_endpoint)

        self._update_provider_controls()
        self._update_save_buttons()

    def _update_provider_controls(self):
        location = self._location_key()
        provider = self._provider_key()

        is_local = location == "local"
        is_remote = location == "remote"
        is_stub = provider == "stub"
        is_ollama = provider == "ollama"

        show_endpoint = is_ollama or is_remote
        show_api_key = is_remote
        show_models = is_ollama or is_remote
        show_ollama_path = is_ollama
        show_refresh_models = is_ollama

        self._set_row_visible(self.provider_endpoint_label, self.provider_endpoint_edit, show_endpoint)
        self._set_row_visible(self.api_key_label, self.api_key_edit, show_api_key)
        self._set_row_visible(self.command_model_label, self.command_model_row_widget, show_models)
        self._set_row_visible(self.chat_model_label, self.chat_model_row_widget, show_models)
        self._set_row_visible(self.ollama_models_path_label, self.ollama_models_path_edit, show_ollama_path)

        self.refresh_models_btn.setVisible(show_refresh_models)
        self.refresh_models_btn.setEnabled(show_refresh_models)

        self.check_server_btn.setVisible(not is_stub)
        self.check_model_btn.setVisible(not is_stub)
        self.check_server_btn.setEnabled(is_ollama)
        self.check_model_btn.setEnabled(is_ollama)

        if is_stub:
            self.future_provider_hint.setText(
                "Выбрана заглушка. Настоящая языковая модель не используется. "
                "Ассистент сможет работать по обычным правилам без ИИ."
            )
        elif is_ollama:
            self.future_provider_hint.setText(
                "Ollama работает локально. Для неё обычно нужен адрес http://localhost:11434 и выбранная локальная модель."
            )
        elif is_remote:
            self.future_provider_hint.setText(
                "Удалённые провайдеры подготовлены в интерфейсе, но в текущем AI gateway выполнение команд через них ещё не подключено."
            )
        else:
            self.future_provider_hint.setText("")

    def _set_combo_text(self, combo: QComboBox, text: str, add_empty: bool = False):
        combo.clear()

        if add_empty:
            combo.addItem("")

        if text:
            combo.addItem(text)
            combo.setCurrentText(text)
        elif add_empty:
            combo.setCurrentIndex(0)

    def _detect_location_from_provider(self, provider: str, saved_location: str | None = None) -> str:
        if saved_location in {"local", "remote"}:
            return saved_location

        remote_keys = {key for key, _label in REMOTE_PROVIDER_OPTIONS}
        if provider in remote_keys:
            return "remote"

        return "local"

    def _load_from_settings(self, reset_dirty: bool):
        self._loading_controls = True

        self.config = settings_service.get_all()
        ai = self.config.get("ai", {})

        provider = ai.get("provider", "stub")
        location = self._detect_location_from_provider(provider, ai.get("provider_location"))

        self.apply_to_all_checkbox.setChecked(ai.get("apply_to_all_commands", True))
        self.enabled_checkbox.setChecked(ai.get("enabled", True))

        self._set_location_key(location)
        self._populate_provider_combo(location, provider)

        if provider == "ollama":
            endpoint = ai.get("ollama_host", "http://localhost:11434")
            command_model = ai.get("ollama_model", "")
            chat_model = ai.get("chat_ollama_model", "")
        elif provider == "stub":
            endpoint = ""
            command_model = ""
            chat_model = ""
        else:
            endpoint = ai.get("provider_endpoint", DEFAULT_ENDPOINTS.get(provider, ""))
            command_model = ai.get("remote_model", "")
            chat_model = ai.get("remote_chat_model", "")

        self.provider_endpoint_edit.setText(endpoint)
        self.api_key_edit.setText(ai.get("api_key", ""))

        self._set_combo_text(self.command_model_combo, command_model, add_empty=False)
        self._set_combo_text(self.chat_model_combo, chat_model, add_empty=True)

        self.ollama_models_path_edit.setText(ai.get("ollama_models_path", ""))
        self.speak_checkbox.setChecked(ai.get("speak_responses", True))

        self._loading_controls = False
        self._update_provider_controls()

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self._set_save_buttons_enabled(self._dirty)
        self.refresh_status()

    def _capture_form_state(self) -> dict:
        return {
            "enabled": self.enabled_checkbox.isChecked(),
            "apply_to_all_commands": self.apply_to_all_checkbox.isChecked(),
            "provider_location": self._location_key(),
            "provider": self._provider_key(),
            "provider_endpoint": self.provider_endpoint_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "command_model": self.command_model_combo.currentText().strip(),
            "chat_model": self.chat_model_combo.currentText().strip(),
            "ollama_models_path": self.ollama_models_path_edit.text().strip(),
            "speak_responses": self.speak_checkbox.isChecked(),
        }

    def _set_save_buttons_enabled(self, enabled: bool):
        self.save_bar.set_dirty(enabled)

    def _update_save_buttons(self):
        if self._loading_controls:
            return

        self._dirty = self._capture_form_state() != self._saved_form_state
        self._set_save_buttons_enabled(self._dirty)
        self.refresh_status()

    def _model_availability_text(self) -> str:
        state = self._capture_form_state()

        if not state["enabled"]:
            return "Модель: не выбрана"

        if not state["apply_to_all_commands"]:
            return "Модель: не используется"

        provider = state["provider"]
        model = state["command_model"]

        if provider == "stub":
            return "Модель: не выбрана"

        if not model:
            return "Модель: не выбрана"

        if provider not in SUPPORTED_RUNTIME_PROVIDERS:
            return "Модель: провайдер не подключён"

        if self.last_model_check_ok is False:
            return "Модель: недоступна"

        return "Модель: доступна"

    def _ai_status(self) -> tuple[str, str, str]:
        state = self._capture_form_state()

        enabled = state["enabled"]
        apply_to_all = state["apply_to_all_commands"]
        provider = state["provider"]
        location = state["provider_location"]
        endpoint = state["provider_endpoint"]
        api_key = state["api_key"]
        model = state["command_model"]

        if self._check_in_progress:
            return "Проверяется", "process", "Выполняется проверка доступности ИИ."

        if not enabled:
            return "Не работает", "bad", "ИИ выключен в настройках."

        if not apply_to_all:
            return "Выключен", "bad", "Интеллектуальная обработка всех команд выключена."

        if provider == "stub":
            return (
                "Не работает",
                "bad",
                "В настройках ИИ не выбрана настоящая модель для интеллектуальной обработки команд."
            )

        if not model:
            return (
                "Не работает",
                "bad",
                "В настройках ИИ не выбрана ни одна модель для обработки команд."
            )

        if provider == "ollama":
            if not endpoint:
                return "Не работает", "bad", "Для Ollama нужно указать адрес локального сервера."

            if self.last_model_check_ok is False:
                return "Не работает", "bad", self.last_model_check_message or "Последняя проверка модели завершилась ошибкой."

            if self.last_model_check_ok is True:
                return "Активно", "ok", self.last_model_check_message or "Модель Ollama успешно проверена."

            return "Настроено", "ok", "Модель указана. Можно проверить её доступность кнопкой «Проверить модель»."

        if location == "remote":
            if not endpoint:
                return (
                    "Не работает",
                    "bad",
                    "Для выбранного удалённого провайдера нужно указать адрес API."
                )

            if not api_key:
                return (
                    "Не работает",
                    "bad",
                    "Для выбранного удалённого провайдера нужно указать API-ключ."
                )

            return (
                "Не поддерживается",
                "bad",
                "Удалённый провайдер настроен, но выполнение команд через него ещё не подключено в AI gateway."
            )

        return "Не работает", "bad", "ИИ сейчас недоступен по неизвестной причине."

    def refresh_status(self):
        status_text, status_kind, status_tip = self._ai_status()

        self.overall_status.setText(status_text)
        self.overall_status.setToolTip(status_tip)
        _apply_status_style(self.overall_status, status_kind)

        self.model_label.setText(self._model_availability_text())
        self.model_label.setToolTip(
            "Здесь показывается только доступность модели. Конкретный провайдер, адрес API и название модели находятся в расширенных настройках."
        )

    def load_models(self):
        if self._provider_key() != "ollama":
            self.check_status_label.setText("Автоматическое обновление списка моделей сейчас доступно только для Ollama.")
            return

        if self._models_thread is not None:
            self.check_status_label.setText("Список моделей уже обновляется.")
            return

        logger.info("AISettingsWidget | load_models_start")

        models_path = self.ollama_models_path_edit.text().strip()

        self.refresh_models_btn.setEnabled(False)
        self.refresh_models_btn.setText("Обновляю...")
        self.check_status_label.setText("Обновляю список моделей Ollama...")

        self._models_thread = QThread()
        self._models_worker = OllamaModelsLoadWorker(models_path)
        self._models_worker.moveToThread(self._models_thread)

        self._models_thread.started.connect(self._models_worker.run)
        self._models_worker.finished.connect(self._on_models_loaded)
        self._models_worker.finished.connect(self._models_thread.quit)
        self._models_worker.finished.connect(self._models_worker.deleteLater)
        self._models_thread.finished.connect(self._models_thread.deleteLater)
        self._models_thread.finished.connect(self._clear_models_worker_refs)

        self._models_thread.start()

    def _on_models_loaded(self, models: list, error: str):
        logger.info("AISettingsWidget | load_models_done | count=%s | error=%s", len(models), error)

        current_main = self.command_model_combo.currentText().strip()
        current_chat = self.chat_model_combo.currentText().strip()

        self._loading_controls = True

        self.command_model_combo.clear()
        self.chat_model_combo.clear()

        if models:
            self.command_model_combo.addItems(models)
            self.chat_model_combo.addItem("")
            self.chat_model_combo.addItems(models)

            if current_main:
                idx = self.command_model_combo.findText(current_main)
                if idx >= 0:
                    self.command_model_combo.setCurrentIndex(idx)
                else:
                    self.command_model_combo.setEditText(current_main)

            if current_chat:
                idx = self.chat_model_combo.findText(current_chat)
                if idx >= 0:
                    self.chat_model_combo.setCurrentIndex(idx)
                else:
                    self.chat_model_combo.setEditText(current_chat)

            self.check_status_label.setText(f"Список моделей обновлён. Найдено: {len(models)}")
        else:
            self._set_combo_text(self.command_model_combo, current_main, add_empty=False)
            self._set_combo_text(self.chat_model_combo, current_chat, add_empty=True)

            if error:
                self.check_status_label.setText(f"Не удалось обновить список моделей: {error}")
            else:
                self.check_status_label.setText("Модели не найдены. Сохранённые значения оставлены.")

        self._loading_controls = False

        self.refresh_models_btn.setEnabled(self._provider_key() == "ollama")
        self.refresh_models_btn.setText("Обновить список моделей")
        self._update_save_buttons()

    def _clear_models_worker_refs(self):
        self._models_worker = None
        self._models_thread = None

    def _start_check(self, mode: str):
        provider = self._provider_key()

        if provider != "ollama":
            self.check_status_label.setText(
                "Проверка доступности пока реализована только для Ollama. "
                "Для удалённых провайдеров нужно подключить отдельные provider-классы в AI gateway."
            )
            self.refresh_status()
            return

        if self._check_thread is not None:
            self.check_status_label.setText("Проверка уже выполняется.")
            return

        host = self.provider_endpoint_edit.text().strip()
        model = self.chat_model_combo.currentText().strip() or self.command_model_combo.currentText().strip()

        self._check_in_progress = True
        self.refresh_status()

        self.check_server_btn.setEnabled(False)
        self.check_model_btn.setEnabled(False)
        self.check_status_label.setText("Проверка выполняется...")

        self._check_thread = QThread()
        self._check_worker = OllamaCheckWorker(mode, host, model)
        self._check_worker.moveToThread(self._check_thread)

        self._check_thread.started.connect(self._check_worker.run)
        self._check_worker.finished.connect(self._on_check_finished)
        self._check_worker.finished.connect(self._check_thread.quit)
        self._check_worker.finished.connect(self._check_worker.deleteLater)
        self._check_thread.finished.connect(self._check_thread.deleteLater)
        self._check_thread.finished.connect(self._clear_check_worker_refs)

        self._check_thread.start()

    def _clear_check_worker_refs(self):
        self._check_worker = None
        self._check_thread = None
        self.check_server_btn.setEnabled(self._provider_key() == "ollama")
        self.check_model_btn.setEnabled(self._provider_key() == "ollama")

    def _on_check_finished(self, ok: bool, message: str):
        self._check_in_progress = False
        self.last_model_check_ok = ok
        self.last_model_check_message = message

        self.check_status_label.setText(message.replace("\n", " | "))
        self.refresh_status()

        if ok:
            self.save_bar.show_saved("Модель доступна!")
        else:
            self.save_bar.show_saved("Проверка не прошла")

    def check_server(self):
        self._start_check("server")

    def check_model(self):
        self._start_check("model")

    def save_settings(self):
        state = self._capture_form_state()
        provider = state["provider"]

        def mutator(cfg: dict):
            cfg.setdefault("ai", {})

            cfg["ai"]["enabled"] = state["enabled"]
            cfg["ai"]["apply_to_all_commands"] = state["apply_to_all_commands"]
            cfg["ai"]["provider_location"] = state["provider_location"]
            cfg["ai"]["provider"] = provider

            cfg["ai"]["provider_endpoint"] = state["provider_endpoint"]
            cfg["ai"]["api_key"] = state["api_key"]
            cfg["ai"]["remote_model"] = (
                state["command_model"]
                if state["provider_location"] == "remote"
                else cfg["ai"].get("remote_model", "")
            )
            cfg["ai"]["remote_chat_model"] = (
                state["chat_model"]
                if state["provider_location"] == "remote"
                else cfg["ai"].get("remote_chat_model", "")
            )

            if provider == "ollama":
                cfg["ai"]["ollama_host"] = state["provider_endpoint"] or "http://localhost:11434"
                cfg["ai"]["ollama_model"] = state["command_model"]
                cfg["ai"]["chat_ollama_model"] = state["chat_model"]
            else:
                # Старые ключи Ollama оставляем, чтобы при возврате к Ollama
                # не потерять ранее выбранную локальную модель.
                cfg["ai"].setdefault("ollama_host", "http://localhost:11434")
                cfg["ai"].setdefault("ollama_model", "")
                cfg["ai"].setdefault("chat_ollama_model", "")

            cfg["ai"]["ollama_models_path"] = state["ollama_models_path"]
            cfg["ai"]["speak_responses"] = state["speak_responses"]

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False

        self.refresh_status()
        self.save_bar.show_saved("Успешно настроено")