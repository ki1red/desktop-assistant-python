from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QMessageBox, QLabel
)

from app.custom_commands.admin import CustomCommandsAdmin


class CustomCommandsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.admin = CustomCommandsAdmin()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Пользовательские команды. Фраза может открывать путь или ссылку."))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            "Фраза", "Тип", "Payload", "Активна"
        ])
        self.table.cellClicked.connect(self.on_row_selected)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.phrase_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["open_path", "open_url"])
        self.payload_edit = QLineEdit()
        self.enabled_checkbox = QCheckBox("Активна")

        form.addRow("Фраза:", self.phrase_edit)
        form.addRow("Тип:", self.type_combo)
        form.addRow("Путь / ссылка:", self.payload_edit)
        form.addRow("", self.enabled_checkbox)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить")
        self.save_btn = QPushButton("Сохранить")
        self.delete_btn = QPushButton("Удалить")

        self.refresh_btn.clicked.connect(self.refresh)
        self.save_btn.clicked.connect(self.save_command)
        self.delete_btn.clicked.connect(self.delete_command)

        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

    def refresh(self):
        rows = self.admin.list_commands()
        self.table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["phrase"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["command_type"]))
            self.table.setItem(i, 2, QTableWidgetItem(row["payload"]))
            self.table.setItem(i, 3, QTableWidgetItem("Да" if row["is_enabled"] else "Нет"))

        self.table.resizeColumnsToContents()

    def on_row_selected(self, row: int, _column: int):
        self.phrase_edit.setText(self.table.item(row, 0).text())
        self.type_combo.setCurrentText(self.table.item(row, 1).text())
        self.payload_edit.setText(self.table.item(row, 2).text())
        self.enabled_checkbox.setChecked(self.table.item(row, 3).text() == "Да")

    def save_command(self):
        phrase = self.phrase_edit.text().strip()
        payload = self.payload_edit.text().strip()

        if not phrase or not payload:
            QMessageBox.warning(self, "Ошибка", "Заполни фразу и путь/ссылку.")
            return

        self.admin.upsert_command(
            phrase=phrase,
            command_type=self.type_combo.currentText(),
            payload=payload,
            is_enabled=self.enabled_checkbox.isChecked()
        )
        self.refresh()
        QMessageBox.information(self, "Готово", "Пользовательская команда сохранена.")

    def delete_command(self):
        phrase = self.phrase_edit.text().strip()
        if not phrase:
            QMessageBox.warning(self, "Ошибка", "Выбери команду для удаления.")
            return

        self.admin.delete_command(phrase)
        self.refresh()
        QMessageBox.information(self, "Готово", "Пользовательская команда удалена.")