from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QMessageBox, QLabel
)

from app.adaptive.quick_access_admin import QuickAccessAdmin


TARGET_TYPE_LABELS = {
    "app": "Приложение",
    "file": "Файл",
    "folder": "Папка",
    "url": "Ссылка"
}

REVERSE_TARGET_TYPE_LABELS = {v: k for k, v in TARGET_TYPE_LABELS.items()}


class QuickTargetsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.admin = QuickAccessAdmin()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Часто используемые и закреплённые цели ассистента."))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Название", "Тип", "Провайдер", "Использований", "Закреплено", "Путь / адрес"
        ])
        self.table.cellClicked.connect(self.on_row_selected)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["app", "file", "folder", "url"])
        self.provider_edit = QLineEdit("local")
        self.path_edit = QLineEdit()
        self.pinned_checkbox = QCheckBox("Закрепить")

        form.addRow("Название:", self.name_edit)
        form.addRow("Тип:", self.type_combo)
        form.addRow("Провайдер:", self.provider_edit)
        form.addRow("Путь / адрес:", self.path_edit)
        form.addRow("", self.pinned_checkbox)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить")
        self.save_btn = QPushButton("Сохранить")
        self.delete_btn = QPushButton("Удалить")

        self.refresh_btn.clicked.connect(self.refresh)
        self.save_btn.clicked.connect(self.save_target)
        self.delete_btn.clicked.connect(self.delete_target)

        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)

    def refresh(self):
        rows = self.admin.list_targets()
        self.table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(TARGET_TYPE_LABELS.get(row["target_type"], row["target_type"])))
            self.table.setItem(i, 2, QTableWidgetItem(row["provider"]))
            self.table.setItem(i, 3, QTableWidgetItem(str(row["usage_count"])))
            self.table.setItem(i, 4, QTableWidgetItem("Да" if row["is_pinned"] else "Нет"))
            self.table.setItem(i, 5, QTableWidgetItem(row["target_path"]))

        self.table.resizeColumnsToContents()

    def on_row_selected(self, row: int, _column: int):
        self.name_edit.setText(self.table.item(row, 0).text())
        type_label = self.table.item(row, 1).text()
        self.type_combo.setCurrentText(REVERSE_TARGET_TYPE_LABELS.get(type_label, type_label))
        self.provider_edit.setText(self.table.item(row, 2).text())
        self.pinned_checkbox.setChecked(self.table.item(row, 4).text() == "Да")
        self.path_edit.setText(self.table.item(row, 5).text())

    def save_target(self):
        name = self.name_edit.text().strip()
        path = self.path_edit.text().strip()

        if not name or not path:
            QMessageBox.warning(self, "Ошибка", "Заполни название и путь.")
            return

        self.admin.upsert_target(
            name=name,
            target_path=path,
            target_type=self.type_combo.currentText(),
            provider=self.provider_edit.text().strip() or "local",
            is_pinned=self.pinned_checkbox.isChecked()
        )
        self.refresh()
        QMessageBox.information(self, "Готово", "Быстрая цель сохранена.")

    def delete_target(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Ошибка", "Выбери цель для удаления.")
            return

        self.admin.delete_target(path)
        self.refresh()
        QMessageBox.information(self, "Готово", "Быстрая цель удалена.")