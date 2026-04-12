from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox, QPushButton, QMessageBox

from app.settings_service import settings_service


class AISettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings_service.get_all()
        self._build_ui()

    def _build_ui(self):
        ai = self.config.get("ai", {})

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.enabled_checkbox = QCheckBox("Включить AI-режим")
        self.enabled_checkbox.setChecked(ai.get("enabled", True))

        self.provider_edit = QLineEdit(ai.get("provider", "stub"))
        self.wake_edit = QLineEdit(", ".join(ai.get("wake_phrases", [])))
        self.stop_edit = QLineEdit(", ".join(ai.get("stop_phrases", [])))

        self.speak_checkbox = QCheckBox("Озвучивать ответы")
        self.speak_checkbox.setChecked(ai.get("speak_responses", True))

        form.addRow("", self.enabled_checkbox)
        form.addRow("Провайдер:", self.provider_edit)
        form.addRow("Фразы включения:", self.wake_edit)
        form.addRow("Фразы выключения:", self.stop_edit)
        form.addRow("", self.speak_checkbox)

        layout.addLayout(form)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

    def save_settings(self):
        wake_phrases = [x.strip() for x in self.wake_edit.text().split(",") if x.strip()]
        stop_phrases = [x.strip() for x in self.stop_edit.text().split(",") if x.strip()]

        def mutator(cfg: dict):
            cfg["ai"]["enabled"] = self.enabled_checkbox.isChecked()
            cfg["ai"]["provider"] = self.provider_edit.text().strip() or "stub"
            cfg["ai"]["wake_phrases"] = wake_phrases
            cfg["ai"]["stop_phrases"] = stop_phrases
            cfg["ai"]["speak_responses"] = self.speak_checkbox.isChecked()

        settings_service.update(mutator)
        QMessageBox.information(self, "Готово", "Настройки AI-режима сохранены.")