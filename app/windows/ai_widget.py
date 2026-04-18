from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QPushButton, QMessageBox, QComboBox, QHBoxLayout, QLabel
)

from app.settings_service import settings_service
from app.ai.ollama_model_discovery import list_available_ollama_models
from app.ai.ollama_health import check_ollama_connection


class AISettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)
        self._build_ui()
        self.load_models()
        self.refresh_status()

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

        self.refresh_models_btn = QPushButton("Обновить список моделей")
        self.refresh_models_btn.clicked.connect(self.load_models)

        model_row = QHBoxLayout()
        model_row.addWidget(self.ollama_model_combo)
        model_row.addWidget(self.refresh_models_btn)

        self.wake_edit = QLineEdit(", ".join(ai.get("wake_phrases", [])))
        self.stop_edit = QLineEdit(", ".join(ai.get("stop_phrases", [])))

        self.speak_checkbox = QCheckBox("Озвучивать ответы")
        self.speak_checkbox.setChecked(ai.get("speak_responses", True))

        form.addRow("", self.enabled_checkbox)
        form.addRow("Провайдер:", self.provider_combo)
        form.addRow("Ollama host:", self.ollama_host_edit)
        form.addRow("Путь к моделям Ollama:", self.ollama_models_path_edit)
        form.addRow("Модель Ollama:", model_row)
        form.addRow("Фразы включения:", self.wake_edit)
        form.addRow("Фразы выключения:", self.stop_edit)
        form.addRow("", self.speak_checkbox)

        layout.addLayout(form)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        buttons_row = QHBoxLayout()
        self.check_btn = QPushButton("Проверить Ollama")
        self.check_btn.clicked.connect(self.check_ollama)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)

        buttons_row.addWidget(self.check_btn)
        buttons_row.addWidget(self.save_btn)

        layout.addLayout(buttons_row)

        self.info_label = QLabel(
            "Список моделей загружается сначала через `ollama list`, "
            "а если не получится — через папку моделей."
        )
        layout.addWidget(self.info_label)

    def refresh_status(self):
        ai = self.config.get("ai", {})
        provider = ai.get("provider", "stub")
        model = ai.get("ollama_model", "")
        host = ai.get("ollama_host", "")
        enabled = ai.get("enabled", True)

        self.status_label.setText(
            f"Статус: enabled={enabled} | provider={provider} | model={model} | host={host}"
        )

    def load_models(self):
        models_path = self.ollama_models_path_edit.text().strip()
        current_saved_model = settings_service.get_section("ai", {}).get("ollama_model", "")

        models = list_available_ollama_models(models_path)

        self.ollama_model_combo.clear()

        if models:
            self.ollama_model_combo.addItems(models)

            index = self.ollama_model_combo.findText(current_saved_model)
            if index >= 0:
                self.ollama_model_combo.setCurrentIndex(index)
            else:
                self.ollama_model_combo.setCurrentIndex(0)
        else:
            if current_saved_model:
                self.ollama_model_combo.setEditText(current_saved_model)

    def check_ollama(self):
        host = self.ollama_host_edit.text().strip()
        model = self.ollama_model_combo.currentText().strip()

        ok, message = check_ollama_connection(host, model)

        if ok:
            QMessageBox.information(self, "Проверка Ollama", message)
        else:
            QMessageBox.warning(self, "Проверка Ollama", message)

    def save_settings(self):
        wake_phrases = [x.strip() for x in self.wake_edit.text().split(",") if x.strip()]
        stop_phrases = [x.strip() for x in self.stop_edit.text().split(",") if x.strip()]
        selected_model = self.ollama_model_combo.currentText().strip()

        def mutator(cfg: dict):
            cfg["ai"]["enabled"] = self.enabled_checkbox.isChecked()
            cfg["ai"]["provider"] = self.provider_combo.currentText()
            cfg["ai"]["ollama_host"] = self.ollama_host_edit.text().strip() or "http://localhost:11434"
            cfg["ai"]["ollama_models_path"] = self.ollama_models_path_edit.text().strip()
            cfg["ai"]["ollama_model"] = selected_model
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
            f"Провайдер: {self.provider_combo.currentText()}\n"
            f"Модель: {selected_model}"
        )