from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit, QHBoxLayout
from PySide6.QtGui import QTextCursor
from pathlib import Path
from PySide6.QtWidgets import QFileDialog
from app.logging.export_logs import build_logs_archive, default_logs_archive_name
from app.logging.ui_logger import log_ui_action

from app.logging_config import LOG_FILE, LOG_DIR


class LogsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.refresh_btn = QPushButton("Обновить")
        self.open_folder_btn = QPushButton("Открыть папку логов")
        self.clear_view_btn = QPushButton("Очистить окно")
        self.export_btn = QPushButton("Скачать логи")

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
        self.export_btn.clicked.connect(self.export_logs)
        self.refresh_btn.clicked.connect(lambda: (log_ui_action("Logs", "refresh"), self.refresh_logs()))
        self.open_folder_btn.clicked.connect(lambda: (log_ui_action("Logs", "open_folder"), self.open_log_folder()))
        self.clear_view_btn.clicked.connect(lambda: (log_ui_action("Logs", "clear_view"), self.text.clear()))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(2000)

        self.refresh_logs()

    def export_logs(self):
        downloads = Path.home() / "Downloads"
        default_name = default_logs_archive_name()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить архив логов",
            str(downloads / default_name),
            "ZIP архив (*.zip)"
        )

        if not path:
            return

        build_logs_archive(path)
        log_ui_action("Logs", "export_logs", path)

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