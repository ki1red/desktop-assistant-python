from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QMessageBox, QLabel
)

from app.providers.provider_admin import ProviderAdmin


PROVIDER_TYPE_LABELS = {
    "web_search": "Веб-поиск",
    "youtube_search": "YouTube поисковик",
    "music_search": "Поиск музыки"
}

REVERSE_PROVIDER_TYPE_LABELS = {v: k for k, v in PROVIDER_TYPE_LABELS.items()}


class ProvidersWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.admin = ProviderAdmin()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Управление провайдерами поиска, YouTube и музыки."))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Ключ", "Тип", "Название", "URL шаблон", "Активен"
        ])
        self.table.cellClicked.connect(self.on_row_selected)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.key_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["web_search", "youtube_search", "music_search"])
        self.title_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.enabled_checkbox = QCheckBox("Активен")

        form.addRow("Ключ:", self.key_edit)
        form.addRow("Тип:", self.type_combo)
        form.addRow("Название:", self.title_edit)
        form.addRow("URL шаблон:", self.url_edit)
        form.addRow("", self.enabled_checkbox)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить")
        self.save_btn = QPushButton("Сохранить")
        self.delete_btn = QPushButton("Удалить")

        self.refresh_btn.clicked.connect(self.refresh)
        self.save_btn.clicked.connect(self.save_provider)
        self.delete_btn.clicked.connect(self.delete_provider)

        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)

    def refresh(self):
        rows = self.admin.list_routes()
        self.table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["provider_key"]))
            self.table.setItem(i, 1, QTableWidgetItem(PROVIDER_TYPE_LABELS.get(row["provider_type"], row["provider_type"])))
            self.table.setItem(i, 2, QTableWidgetItem(row["title"]))
            self.table.setItem(i, 3, QTableWidgetItem(row["url_template"]))
            self.table.setItem(i, 4, QTableWidgetItem("Да" if row["is_enabled"] else "Нет"))

        self.table.resizeColumnsToContents()

    def on_row_selected(self, row: int, _column: int):
        self.key_edit.setText(self.table.item(row, 0).text())
        type_label = self.table.item(row, 1).text()
        self.type_combo.setCurrentText(REVERSE_PROVIDER_TYPE_LABELS.get(type_label, type_label))
        self.title_edit.setText(self.table.item(row, 2).text())
        self.url_edit.setText(self.table.item(row, 3).text())
        self.enabled_checkbox.setChecked(self.table.item(row, 4).text() == "Да")

    def save_provider(self):
        key = self.key_edit.text().strip()
        title = self.title_edit.text().strip()
        url = self.url_edit.text().strip()

        if not key or not title or not url:
            QMessageBox.warning(self, "Ошибка", "Заполни ключ, название и URL шаблон.")
            return

        self.admin.upsert_route(
            provider_key=key,
            provider_type=self.type_combo.currentText(),
            title=title,
            url_template=url,
            is_enabled=self.enabled_checkbox.isChecked()
        )
        self.refresh()
        QMessageBox.information(self, "Готово", "Провайдер сохранён.")

    def delete_provider(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "Ошибка", "Выбери провайдер для удаления.")
            return

        self.admin.delete_route(key)
        self.refresh()
        QMessageBox.information(self, "Готово", "Провайдер удалён.")