from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QPushButton, QMessageBox, QComboBox, QHBoxLayout, QLabel
)

from app.settings_service import settings_service
from app.ai.ollama_model_discovery import list_available_ollama_models
from app.ai.ollama_health import quick_server_check, check_ollama_model
from app.logger import get_logger


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

        self._build_ui()
        self._apply_saved_models_to_combo()
        self.refresh_status()

        # ВАЖНО:
        # Больше НЕ вызываем self.load_models() автоматически при старте.
        # Иначе Ollama / диск / PATH могут подвесить GUI после запуска Windows.
        logger.info("AISettingsWidget | init_done")

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot
        self.refresh_status()

    def _build_ui(self):
        ai = self.config.get("ai", {})

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.enabled_checkbox = QCheckBox("Включить AI-режим")
        self.enabled_checkbox.setChecked(ai.get("enabled", True))

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["stub", "ollama"])
        self.provider_combo.setCurrentText(ai.get("provider", "stub"))

        self.ollama_host_edit = QLineEdit(ai.get("ollama_host", "http://localhost:11434"))
        self.ollama_models_path_edit = QLineEdit(ai.get("ollama_models_path", ""))

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

        self.wake_edit = QLineEdit(", ".join(ai.get("wake_phrases", [])))
        self.stop_edit = QLineEdit(", ".join(ai.get("stop_phrases", [])))

        self.speak_checkbox = QCheckBox("Озвучивать ответы")
        self.speak_checkbox.setChecked(ai.get("speak_responses", True))

        form.addRow("", self.enabled_checkbox)
        form.addRow("Провайдер:", self.provider_combo)
        form.addRow("Ollama host:", self.ollama_host_edit)
        form.addRow("Путь к моделям Ollama:", self.ollama_models_path_edit)
        form.addRow("Основная модель Ollama:", main_model_row)
        form.addRow("Быстрая модель для диалога:", chat_model_row)
        form.addRow("Фразы включения:", self.wake_edit)
        form.addRow("Фразы выключения:", self.stop_edit)
        form.addRow("", self.speak_checkbox)

        layout.addLayout(form)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        self.check_status_label = QLabel("")
        layout.addWidget(self.check_status_label)

        buttons_row = QHBoxLayout()

        self.check_server_btn = QPushButton("Быстрая проверка сервера")
        self.check_server_btn.clicked.connect(self.check_server)

        self.check_model_btn = QPushButton("Проверить выбранную модель")
        self.check_model_btn.clicked.connect(self.check_model)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)

        buttons_row.addWidget(self.check_server_btn)
        buttons_row.addWidget(self.check_model_btn)
        buttons_row.addWidget(self.save_btn)

        layout.addLayout(buttons_row)

        self.info_label = QLabel(
            "Модели Ollama теперь не сканируются автоматически при запуске,\n"
            "чтобы не подвешивать интерфейс после старта Windows.\n"
            "Для обновления списка нажмите «Обновить список моделей»."
        )
        layout.addWidget(self.info_label)

    def _apply_saved_models_to_combo(self):
        ai_cfg = settings_service.get_section("ai", {})

        current_saved_model = ai_cfg.get("ollama_model", "")
        current_chat_model = ai_cfg.get("chat_ollama_model", "")

        self.ollama_model_combo.clear()
        self.chat_ollama_model_combo.clear()

        if current_saved_model:
            self.ollama_model_combo.addItem(current_saved_model)
            self.ollama_model_combo.setCurrentText(current_saved_model)

        self.chat_ollama_model_combo.addItem("")

        if current_chat_model:
            self.chat_ollama_model_combo.addItem(current_chat_model)
            self.chat_ollama_model_combo.setCurrentText(current_chat_model)

    def refresh_status(self):
        ai = self.config.get("ai", {})
        provider = ai.get("provider", "stub")
        model = ai.get("ollama_model", "")
        chat_model = ai.get("chat_ollama_model", "")
        host = ai.get("ollama_host", "")
        enabled = ai.get("enabled", True)

        self.status_label.setText(
            f"Статус: enabled={enabled} | provider={provider} | "
            f"main_model={model} | chat_model={chat_model or '(не задана)'} | host={host}"
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

        ai_cfg = settings_service.get_section("ai", {})
        current_saved_model = ai_cfg.get("ollama_model", "")
        current_chat_model = ai_cfg.get("chat_ollama_model", "")

        self.ollama_model_combo.clear()
        self.chat_ollama_model_combo.clear()

        if models:
            self.ollama_model_combo.addItems(models)

            self.chat_ollama_model_combo.addItem("")
            self.chat_ollama_model_combo.addItems(models)

            index_main = self.ollama_model_combo.findText(current_saved_model)
            if index_main >= 0:
                self.ollama_model_combo.setCurrentIndex(index_main)
            elif current_saved_model:
                self.ollama_model_combo.setEditText(current_saved_model)
            else:
                self.ollama_model_combo.setCurrentIndex(0)

            index_chat = self.chat_ollama_model_combo.findText(current_chat_model)
            if index_chat >= 0:
                self.chat_ollama_model_combo.setCurrentIndex(index_chat)
            elif current_chat_model:
                self.chat_ollama_model_combo.setEditText(current_chat_model)
            else:
                self.chat_ollama_model_combo.setCurrentIndex(0)

            self.check_status_label.setText(f"Список моделей обновлён. Найдено: {len(models)}")
        else:
            if current_saved_model:
                self.ollama_model_combo.addItem(current_saved_model)
                self.ollama_model_combo.setCurrentText(current_saved_model)

            self.chat_ollama_model_combo.addItem("")

            if current_chat_model:
                self.chat_ollama_model_combo.addItem(current_chat_model)
                self.chat_ollama_model_combo.setCurrentText(current_chat_model)

            if error:
                self.check_status_label.setText(f"Не удалось обновить список моделей: {error}")
            else:
                self.check_status_label.setText("Модели не найдены. Сохранённые значения оставлены.")

        self.refresh_models_btn.setEnabled(True)
        self.refresh_models_btn.setText("Обновить список моделей")
        self.refresh_status()

    def _clear_models_worker_refs(self):
        self._models_worker = None
        self._models_thread = None

    def _start_check(self, mode: str):
        if self._check_thread is not None:
            QMessageBox.information(self, "Проверка", "Проверка уже выполняется.")
            return

        host = self.ollama_host_edit.text().strip()
        model = self.chat_ollama_model_combo.currentText().strip() or self.ollama_model_combo.currentText().strip()

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
        self.check_status_label.setText(message.replace("\n", " | "))

        if ok:
            QMessageBox.information(self, "Проверка Ollama", message)
        else:
            QMessageBox.warning(self, "Проверка Ollama", message)

    def check_server(self):
        self._start_check("server")

    def check_model(self):
        self._start_check("model")

    def save_settings(self):
        wake_phrases = [x.strip() for x in self.wake_edit.text().split(",") if x.strip()]
        stop_phrases = [x.strip() for x in self.stop_edit.text().split(",") if x.strip()]
        selected_model = self.ollama_model_combo.currentText().strip()
        selected_chat_model = self.chat_ollama_model_combo.currentText().strip()

        def mutator(cfg: dict):
            cfg["ai"]["enabled"] = self.enabled_checkbox.isChecked()
            cfg["ai"]["provider"] = self.provider_combo.currentText()
            cfg["ai"]["ollama_host"] = self.ollama_host_edit.text().strip() or "http://localhost:11434"
            cfg["ai"]["ollama_models_path"] = self.ollama_models_path_edit.text().strip()
            cfg["ai"]["ollama_model"] = selected_model
            cfg["ai"]["chat_ollama_model"] = selected_chat_model
            cfg["ai"]["wake_phrases"] = wake_phrases
            cfg["ai"]["stop_phrases"] = stop_phrases
            cfg["ai"]["speak_responses"] = self.speak_checkbox.isChecked()

        settings_service.update(mutator)
        self.config = settings_service.get_all()
        self.refresh_status()

        QMessageBox.information(
            self,
            "Готово",
            f"Настройки AI-режима сохранены.\n"
            f"Основная модель: {selected_model}\n"
            f"Быстрая модель для диалога: {selected_chat_model or '(не задана)'}"
        )