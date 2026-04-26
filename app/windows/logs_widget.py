from pathlib import Path
from datetime import datetime
import zipfile

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QTextCursor

from app.logging_config import LOG_FILE, LOG_DIR


try:
    from app.logging.export_logs import build_logs_archive, default_logs_archive_name
except Exception:
    build_logs_archive = None
    default_logs_archive_name = None


try:
    from app.logging.ui_logger import log_ui_action
except Exception:
    def log_ui_action(*_args, **_kwargs):
        return None


def _fallback_logs_archive_name() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"local_assistant_logs_{stamp}.zip"


def _fallback_build_logs_archive(output_path: str):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        if LOG_DIR.exists():
            for item in LOG_DIR.iterdir():
                if item.is_file():
                    zf.write(item, arcname=item.name)


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
        top.addWidget(self.export_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.text)

        self.refresh_btn.clicked.connect(self.on_refresh_clicked)
        self.open_folder_btn.clicked.connect(self.on_open_folder_clicked)
        self.clear_view_btn.clicked.connect(self.on_clear_view_clicked)
        self.export_btn.clicked.connect(self.export_logs)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(2000)

        self.refresh_logs()

    def on_refresh_clicked(self):
        log_ui_action("Logs", "refresh")
        self.refresh_logs()

    def on_open_folder_clicked(self):
        log_ui_action("Logs", "open_folder")
        self.open_log_folder()

    def on_clear_view_clicked(self):
        log_ui_action("Logs", "clear_view")
        self.text.clear()

    def export_logs(self):
        downloads = Path.home() / "Downloads"

        if default_logs_archive_name is not None:
            default_name = default_logs_archive_name()
        else:
            default_name = _fallback_logs_archive_name()

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить архив логов",
            str(downloads / default_name),
            "ZIP архив (*.zip)"
        )

        if not path:
            return

        try:
            if build_logs_archive is not None:
                build_logs_archive(path)
            else:
                _fallback_build_logs_archive(path)

            log_ui_action("Logs", "export_logs", path)

            QMessageBox.information(
                self,
                "Готово",
                f"Архив логов сохранён:\n{path}"
            )

        except Exception as e:
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось сохранить архив логов:\n{e}"
            )

    def refresh_logs(self):
        try:
            if LOG_FILE.exists():
                content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                self.text.setPlainText(content[-50000:])
                self.text.moveCursor(QTextCursor.End)
            else:
                self.text.setPlainText(f"Файл логов пока не найден:\n{LOG_FILE}")
        except Exception as e:
            self.text.setPlainText(f"Ошибка чтения логов: {e}")

    def open_log_folder(self):
        import os

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOG_DIR))