from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QCheckBox, QPushButton, QMessageBox
)

from app.settings_service import settings_service


class VoiceSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings_service.get_all()
        self._build_ui()

    def _build_ui(self):
        voice = self.config["voice"]

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.enabled_checkbox = QCheckBox("Включить голосовые ответы")
        self.enabled_checkbox.setChecked(voice.get("enabled", True))

        self.rate_edit = QLineEdit(str(voice.get("rate", 185)))
        self.volume_edit = QLineEdit(str(voice.get("volume", 1.0)))
        self.heartbeat_edit = QLineEdit(str(voice.get("heartbeat_interval_sec", 8)))

        form.addRow("", self.enabled_checkbox)
        form.addRow("Скорость речи:", self.rate_edit)
        form.addRow("Громкость:", self.volume_edit)
        form.addRow("Интервал фразы 'ещё работаю' (сек):", self.heartbeat_edit)

        layout.addLayout(form)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

    def save_settings(self):
        def mutator(cfg: dict):
            cfg["voice"]["enabled"] = self.enabled_checkbox.isChecked()
            cfg["voice"]["rate"] = int(self.rate_edit.text().strip())
            cfg["voice"]["volume"] = float(self.volume_edit.text().strip())
            cfg["voice"]["heartbeat_interval_sec"] = int(self.heartbeat_edit.text().strip())

        settings_service.update(mutator)
        QMessageBox.information(self, "Готово", "Голосовые настройки сохранены и применены.")