from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
    QLabel,
    QGridLayout,
)
from PySide6.QtGui import QTextCursor

from app.logging_config import LOG_FILE, LOG_DIR
from app.logging.export_logs import build_logs_archive, default_logs_archive_name
from app.windows.ui_kit import make_page_title, InfoCard


try:
    from app.logging.ui_logger import log_ui_action
except Exception:
    def log_ui_action(*_args, **_kwargs):
        return None


class LogsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self._last_content = ""
        self._force_scroll_to_bottom = True

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(2000)

        self.refresh_logs(force_scroll_to_bottom=True)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = make_page_title("Логи")
        header.addWidget(title, 0, 1)

        root.addLayout(header)

        card = InfoCard()

        info = QLabel(
            "Здесь отображается журнал текущего запуска ассистента. "
            "При скачивании будет сохранён архив со всеми логами из папки."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 18px; color: #303846;")
        info.setToolTip(
            "Логи — это технический журнал. В нём видны запуск приложения, настройки, распознавание речи, команды и ошибки."
        )

        path_label = QLabel(f"Текущий файл логов: {LOG_FILE}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("font-size: 14px; color: #687386;")
        path_label.setToolTip("Это путь к файлу логов текущего запуска приложения.")

        folder_label = QLabel(f"Папка логов: {LOG_DIR}")
        folder_label.setWordWrap(True)
        folder_label.setStyleSheet("font-size: 14px; color: #687386;")
        folder_label.setToolTip("При скачивании логов в архив попадут все файлы из этой папки.")

        card.layout.addWidget(info)
        card.layout.addWidget(path_label)
        card.layout.addWidget(folder_label)

        buttons = QHBoxLayout()

        self.open_folder_btn = QPushButton("Открыть папку логов")
        self.clear_view_btn = QPushButton("Очистить окно")
        self.export_btn = QPushButton("Скачать все логи")

        self.open_folder_btn.setToolTip("Открывает папку, где хранятся файлы логов ассистента.")
        self.clear_view_btn.setToolTip("Очищает только отображение в этом окне. Сам файл логов не удаляется.")
        self.export_btn.setToolTip("Сохраняет ZIP-архив со всеми логами из папки логов.")

        self.open_folder_btn.clicked.connect(self.on_open_folder_clicked)
        self.clear_view_btn.clicked.connect(self.on_clear_view_clicked)
        self.export_btn.clicked.connect(self.export_logs)

        buttons.addWidget(self.open_folder_btn)
        buttons.addWidget(self.clear_view_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.export_btn)

        card.layout.addLayout(buttons)

        root.addWidget(card)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("""
            QTextEdit {
                font-size: 13px;
                font-family: Consolas, monospace;
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #d6d9e0;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        self.text.setToolTip(
            "Последние строки текущего файла логов. Если вы прокрутите текст вручную, автообновление не вернёт вас вниз."
        )

        root.addWidget(self.text, 1)

    def on_tab_activated(self):
        # При возврате на вкладку можно снова автоматически перейти вниз.
        self.refresh_logs(force_scroll_to_bottom=True)

    def on_open_folder_clicked(self):
        log_ui_action("Logs", "open_folder")
        self.open_log_folder()

    def on_clear_view_clicked(self):
        log_ui_action("Logs", "clear_view")
        self.text.clear()
        self._last_content = ""

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

        try:
            saved_path = build_logs_archive(path)
            log_ui_action("Logs", "export_logs", str(saved_path))

            QMessageBox.information(
                self,
                "Готово",
                f"Архив со всеми логами сохранён:\n{saved_path}"
            )

        except Exception as e:
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Не удалось сохранить архив логов:\n{e}"
            )

    def refresh_logs(self, force_scroll_to_bottom: bool = False):
        try:
            if not LOG_FILE.exists():
                content = f"Файл логов текущего запуска пока не найден:\n{LOG_FILE}"
            else:
                content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                content = content[-80000:]

            if content == self._last_content and not force_scroll_to_bottom:
                return

            scrollbar = self.text.verticalScrollBar()
            old_value = scrollbar.value()
            old_maximum = scrollbar.maximum()

            # Пользователь считается находящимся внизу, если скролл почти в самом конце.
            was_at_bottom = old_value >= old_maximum - 8

            self.text.setPlainText(content)
            self._last_content = content

            if force_scroll_to_bottom or was_at_bottom:
                self.text.moveCursor(QTextCursor.End)
            else:
                # Если пользователь читает середину логов, сохраняем позицию.
                scrollbar.setValue(min(old_value, scrollbar.maximum()))

        except Exception as e:
            self.text.setPlainText(f"Ошибка чтения логов: {e}")

    def open_log_folder(self):
        import os

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOG_DIR))