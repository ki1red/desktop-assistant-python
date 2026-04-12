from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QMessageBox, QCheckBox

from app.settings_service import settings_service


class BackgroundSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings_service.get_all()
        self._build_ui()

    def _build_ui(self):
        bg = self.config["background"]

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.hotkey_edit = QLineEdit(bg.get("hotkey", "<ctrl>+<alt>+<space>"))
        self.cancel_checkbox = QCheckBox("Повторное нажатие отменяет текущую операцию")
        self.cancel_checkbox.setChecked(bg.get("double_press_cancels", True))

        form.addRow("Горячая клавиша:", self.hotkey_edit)
        form.addRow("", self.cancel_checkbox)

        layout.addLayout(form)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

    def save_settings(self):
        hotkey = self.hotkey_edit.text().strip()
        if not hotkey:
            QMessageBox.warning(self, "Ошибка", "Горячая клавиша не может быть пустой.")
            return

        def mutator(cfg: dict):
            cfg["background"]["hotkey"] = hotkey
            cfg["background"]["double_press_cancels"] = self.cancel_checkbox.isChecked()

        settings_service.update(mutator)
        QMessageBox.information(self, "Готово", "Настройки фонового режима сохранены и применены.")