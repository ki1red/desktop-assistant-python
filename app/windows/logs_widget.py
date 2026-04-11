from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit, QHBoxLayout
from PySide6.QtGui import QTextCursor

from app.logging_config import LOG_FILE, LOG_DIR


class LogsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.refresh_btn = QPushButton("Обновить")
        self.open_folder_btn = QPushButton("Открыть папку логов")
        self.clear_view_btn = QPushButton("Очистить окно")

        top = QHBoxLayout()
        top.addWidget(self.refresh_btn)
        top.addWidget(self.open_folder_btn)
        top.addWidget(self.clear_view_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.text)

        self.refresh_btn.clicked.connect(self.refresh_logs)
        self.open_folder_btn.clicked.connect(self.open_log_folder)
        self.clear_view_btn.clicked.connect(self.text.clear)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(2000)

        self.refresh_logs()

    def refresh_logs(self):
        try:
            if LOG_FILE.exists():
                content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                self.text.setPlainText(content[-50000:])
                self.text.moveCursor(QTextCursor.End)
        except Exception as e:
            self.text.setPlainText(f"Ошибка чтения логов: {e}")

    def open_log_folder(self):
        import os
        os.startfile(str(LOG_DIR))