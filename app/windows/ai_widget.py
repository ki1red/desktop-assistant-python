from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
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
        header.addWidget(self.overall_status, 0, 2, alignment=Qt.AlignRight | Qt.AlignVCenter)

        root.addLayout(header)

        card = InfoCard()

        self.model_label = QLabel()
        self.model_label.setStyleSheet("font-size: 24px; font-weight: 500;")
        self.model_label.setToolTip(
            "Здесь показывается только доступность модели. Название модели и провайдер находятся в расширенных настройках."
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

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        self.enabled_checkbox = QCheckBox("Включить ИИ-режим")

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["stub", "ollama"])

        self.ollama_host_edit = QLineEdit()
        self.ollama_models_path_edit = QLineEdit()

        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setEditable(True)
        self.ollama_model_combo.setInsertPolicy(QComboBox.NoInsert)

        self.chat_ollama_model_combo = QComboBox()
        self.chat_ollama_model_combo.setEditable(True)
        self.chat_ollama_model_combo.setInsertPolicy(QComboBox.NoInsert)

        self.refresh_models_btn = QPushButton("Обновить список моделей")
        self.refresh_models_btn.clicked.connect(self.load_models)

        main_model_row = QHBoxLayout()
        main_model_row.addWidget(self.ollama_model_combo)
        main_model_row.addWidget(self.refresh_models_btn)

        chat_model_row = QHBoxLayout()
        chat_model_row.addWidget(self.chat_ollama_model_combo)

        self.wake_edit = QLineEdit()
        self.stop_edit = QLineEdit()

        self.speak_checkbox = QCheckBox("Озвучивать ответы")

        form.addRow("", self.enabled_checkbox)
        form.addRow("Провайдер:", self.provider_combo)
        form.addRow("Ollama host:", self.ollama_host_edit)
        form.addRow("Путь к моделям Ollama:", self.ollama_models_path_edit)
        form.addRow("Основная модель:", main_model_row)
        form.addRow("Быстрая модель для диалога:", chat_model_row)
        form.addRow("Фразы включения:", self.wake_edit)
        form.addRow("Фразы выключения:", self.stop_edit)
        form.addRow("", self.speak_checkbox)

        advanced_layout.addLayout(form)

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

        self.save_bar = FloatingSaveBar(self, "Сохранить настройки ИИ")
        self.save_bar.clicked.connect(self.save_settings)

    def _connect_change_signals(self):
        self.apply_to_all_checkbox.stateChanged.connect(self._update_save_buttons)
        self.enabled_checkbox.stateChanged.connect(self._update_save_buttons)
        self.provider_combo.currentTextChanged.connect(self._update_save_buttons)
        self.ollama_host_edit.textChanged.connect(self._update_save_buttons)
        self.ollama_models_path_edit.textChanged.connect(self._update_save_buttons)
        self.ollama_model_combo.currentTextChanged.connect(self._update_save_buttons)
        self.chat_ollama_model_combo.currentTextChanged.connect(self._update_save_buttons)
        self.wake_edit.textChanged.connect(self._update_save_buttons)
        self.stop_edit.textChanged.connect(self._update_save_buttons)
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

    def _set_combo_text(self, combo: QComboBox, text: str, add_empty: bool = False):
        combo.clear()

        if add_empty:
            combo.addItem("")

        if text:
            combo.addItem(text)
            combo.setCurrentText(text)
        elif add_empty:
            combo.setCurrentIndex(0)

    def _load_from_settings(self, reset_dirty: bool):
        self._loading_controls = True

        self.config = settings_service.get_all()
        ai = self.config.get("ai", {})

        self.apply_to_all_checkbox.setChecked(ai.get("apply_to_all_commands", True))
        self.enabled_checkbox.setChecked(ai.get("enabled", True))
        self.provider_combo.setCurrentText(ai.get("provider", "stub"))
        self.ollama_host_edit.setText(ai.get("ollama_host", "http://localhost:11434"))
        self.ollama_models_path_edit.setText(ai.get("ollama_models_path", ""))

        self._set_combo_text(self.ollama_model_combo, ai.get("ollama_model", ""), add_empty=False)
        self._set_combo_text(self.chat_ollama_model_combo, ai.get("chat_ollama_model", ""), add_empty=True)

        self.wake_edit.setText(", ".join(ai.get("wake_phrases", [])))
        self.stop_edit.setText(", ".join(ai.get("stop_phrases", [])))
        self.speak_checkbox.setChecked(ai.get("speak_responses", True))

        self._loading_controls = False

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self._set_save_buttons_enabled(self._dirty)
        self.refresh_status()

    def _split_phrases(self, text: str) -> list[str]:
        return [x.strip() for x in text.split(",") if x.strip()]

    def _capture_form_state(self) -> dict:
        return {
            "enabled": self.enabled_checkbox.isChecked(),
            "apply_to_all_commands": self.apply_to_all_checkbox.isChecked(),
            "provider": self.provider_combo.currentText().strip(),
            "ollama_host": self.ollama_host_edit.text().strip() or "http://localhost:11434",
            "ollama_models_path": self.ollama_models_path_edit.text().strip(),
            "ollama_model": self.ollama_model_combo.currentText().strip(),
            "chat_ollama_model": self.chat_ollama_model_combo.currentText().strip(),
            "wake_phrases": self._split_phrases(self.wake_edit.text()),
            "stop_phrases": self._split_phrases(self.stop_edit.text()),
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
            return "Модель: недоступна"

        if state["provider"] != "ollama":
            return "Модель: недоступна"

        if not state["ollama_model"]:
            return "Модель: недоступна"

        if self.last_model_check_ok is False:
            return "Модель: недоступна"

        return "Модель: доступна"

    def _ai_status(self) -> tuple[str, str, str]:
        state = self._capture_form_state()

        enabled = state["enabled"]
        provider = state["provider"]
        model = state["ollama_model"]
        host = state["ollama_host"]

        if self._check_in_progress:
            return "Проверяется", "process", "Выполняется проверка доступности ИИ."

        if not enabled:
            return "Не работает", "bad", "ИИ выключен в настройках."

        if provider == "stub":
            return "Не работает", "bad", "Выбрана встроенная заглушка StubAIProvider. Настоящая языковая модель не используется."

        if provider == "ollama":
            if not host or not model:
                return "Не работает", "bad", "Для Ollama нужно указать host и модель в расширенных настройках."

            if self.last_model_check_ok is False:
                return "Не работает", "bad", self.last_model_check_message or "Последняя проверка модели завершилась ошибкой."

            if self.last_model_check_ok is True:
                return "Активно", "ok", self.last_model_check_message or "Модель Ollama успешно проверена."

            return "Настроено", "ok", "Модель указана. Можно проверить её доступность кнопкой «Проверить модель»."

        return "Не работает", "bad", f"Неизвестный AI-провайдер: {provider}"

    def refresh_status(self):
        status_text, status_kind, status_tip = self._ai_status()

        self.overall_status.setText(status_text)
        self.overall_status.setToolTip(status_tip)
        _apply_status_style(self.overall_status, status_kind)

        self.model_label.setText(self._model_availability_text())
        self.model_label.setToolTip(
            "Здесь показывается только доступность модели. Конкретный провайдер и название модели находятся в расширенных настройках."
        )

    def load_models(self):
        if self._models_thread is not None:
            QMessageBox.information(self, "Модели Ollama", "Список моделей уже обновляется.")
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

        current_main = self.ollama_model_combo.currentText().strip()
        current_chat = self.chat_ollama_model_combo.currentText().strip()

        self._loading_controls = True

        self.ollama_model_combo.clear()
        self.chat_ollama_model_combo.clear()

        if models:
            self.ollama_model_combo.addItems(models)
            self.chat_ollama_model_combo.addItem("")
            self.chat_ollama_model_combo.addItems(models)

            if current_main:
                idx = self.ollama_model_combo.findText(current_main)
                if idx >= 0:
                    self.ollama_model_combo.setCurrentIndex(idx)
                else:
                    self.ollama_model_combo.setEditText(current_main)

            if current_chat:
                idx = self.chat_ollama_model_combo.findText(current_chat)
                if idx >= 0:
                    self.chat_ollama_model_combo.setCurrentIndex(idx)
                else:
                    self.chat_ollama_model_combo.setEditText(current_chat)

            self.check_status_label.setText(f"Список моделей обновлён. Найдено: {len(models)}")
        else:
            self._set_combo_text(self.ollama_model_combo, current_main, add_empty=False)
            self._set_combo_text(self.chat_ollama_model_combo, current_chat, add_empty=True)

            if error:
                self.check_status_label.setText(f"Не удалось обновить список моделей: {error}")
            else:
                self.check_status_label.setText("Модели не найдены. Сохранённые значения оставлены.")

        self._loading_controls = False

        self.refresh_models_btn.setEnabled(True)
        self.refresh_models_btn.setText("Обновить список моделей")
        self._update_save_buttons()

    def _clear_models_worker_refs(self):
        self._models_worker = None
        self._models_thread = None

    def _start_check(self, mode: str):
        if self._check_thread is not None:
            QMessageBox.information(self, "Проверка", "Проверка уже выполняется.")
            return

        host = self.ollama_host_edit.text().strip()
        model = self.chat_ollama_model_combo.currentText().strip() or self.ollama_model_combo.currentText().strip()

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
        self.check_server_btn.setEnabled(True)
        self.check_model_btn.setEnabled(True)

    def _on_check_finished(self, ok: bool, message: str):
        self._check_in_progress = False
        self.last_model_check_ok = ok
        self.last_model_check_message = message

        self.check_status_label.setText(message.replace("\n", " | "))
        self.refresh_status()

        if ok:
            self.save_bar.show_saved("Модель доступна!")
        else:
            QMessageBox.warning(self, "Проверка Ollama", message)

    def check_server(self):
        self._start_check("server")

    def check_model(self):
        self._start_check("model")

    def save_settings(self):
        state = self._capture_form_state()

        def mutator(cfg: dict):
            cfg.setdefault("ai", {})
            cfg["ai"]["enabled"] = state["enabled"]
            cfg["ai"]["apply_to_all_commands"] = state["apply_to_all_commands"]
            cfg["ai"]["provider"] = state["provider"]
            cfg["ai"]["ollama_host"] = state["ollama_host"]
            cfg["ai"]["ollama_models_path"] = state["ollama_models_path"]
            cfg["ai"]["ollama_model"] = state["ollama_model"]
            cfg["ai"]["chat_ollama_model"] = state["chat_ollama_model"]
            cfg["ai"]["wake_phrases"] = state["wake_phrases"]
            cfg["ai"]["stop_phrases"] = state["stop_phrases"]
            cfg["ai"]["speak_responses"] = state["speak_responses"]

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False

        self.refresh_status()
        self.save_bar.show_saved("Сохранено!")