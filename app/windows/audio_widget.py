from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QMessageBox
)

from app.settings_service import settings_service


class AudioSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings_service.get_all()
        self._build_ui()

    def _build_ui(self):
        audio = self.config["audio"]

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.max_record_edit = QLineEdit(str(audio.get("max_record_seconds", 12)))
        self.min_record_edit = QLineEdit(str(audio.get("min_record_seconds", 0.8)))
        self.silence_stop_edit = QLineEdit(str(audio.get("silence_duration_stop_sec", 1.0)))
        self.silence_threshold_edit = QLineEdit(str(audio.get("silence_threshold", 500)))

        form.addRow("Максимальная длина записи (сек):", self.max_record_edit)
        form.addRow("Минимальная длина записи (сек):", self.min_record_edit)
        form.addRow("Пауза для остановки (сек):", self.silence_stop_edit)
        form.addRow("Порог тишины:", self.silence_threshold_edit)

        layout.addLayout(form)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

    def save_settings(self):
        def mutator(cfg: dict):
            cfg["audio"]["max_record_seconds"] = float(self.max_record_edit.text().strip())
            cfg["audio"]["min_record_seconds"] = float(self.min_record_edit.text().strip())
            cfg["audio"]["silence_duration_stop_sec"] = float(self.silence_stop_edit.text().strip())
            cfg["audio"]["silence_threshold"] = int(self.silence_threshold_edit.text().strip())

        settings_service.update(mutator)
        QMessageBox.information(self, "Готово", "Настройки записи сохранены и применены.")