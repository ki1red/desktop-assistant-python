from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLineEdit, QMessageBox, QLabel
)

from app.config_loader import ConfigLoader


class PathsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.loader = ConfigLoader()
        self.config = self.loader.get()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Папки, которые ассистент должен проверять в первую очередь."))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.add_btn = QPushButton("Добавить")
        self.remove_btn = QPushButton("Удалить выбранную")
        self.save_btn = QPushButton("Сохранить")

        self.add_btn.clicked.connect(self.add_path)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.save_btn.clicked.connect(self.save_paths)

        row.addWidget(self.path_edit)
        row.addWidget(self.add_btn)
        row.addWidget(self.remove_btn)
        row.addWidget(self.save_btn)

        layout.addLayout(row)

    def refresh(self):
        self.list_widget.clear()
        for path in self.config["priority_roots"].get("extra_paths", []):
            self.list_widget.addItem(path)

    def add_path(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        self.list_widget.addItem(path)
        self.path_edit.clear()

    def remove_selected(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def save_paths(self):
        paths = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        self.config["priority_roots"]["extra_paths"] = paths
        self.loader.save(self.config)
        QMessageBox.information(self, "Готово", "Папки сохранены.\nДля обновления индекса запусти перестроение.")