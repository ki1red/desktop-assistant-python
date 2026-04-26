from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.windows.logs_widget import LogsWidget
from app.windows.providers_widget import ProvidersWidget
from app.windows.quick_targets_widget import QuickTargetsWidget
from app.windows.paths_widget import PathsWidget
from app.windows.audio_widget import AudioSettingsWidget
from app.windows.history_widget import HistoryWidget
from app.windows.custom_commands_widget import CustomCommandsWidget
from app.windows.status_widget import StatusWidget
from app.windows.ai_widget import AISettingsWidget
from app.logger import get_logger


logger = get_logger("ui")


class AssistantMainWindow(QMainWindow):
    def __init__(self, bg_service):
        logger.info("UI | MainWindow | init_start")

        super().__init__()
        self.setWindowTitle("Local PC Assistant")
        self.resize(1250, 860)

        self.setStyleSheet("""
            QMainWindow {
                background: #f7f8fb;
            }

            QTabWidget::pane {
                border: 1px solid #d6d9e0;
                background: #ffffff;
                border-radius: 10px;
            }

            QTabBar::tab {
                font-size: 15px;
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                background: #eceff5;
            }

            QTabBar::tab:selected {
                background: #ffffff;
                font-weight: 600;
            }

            QLabel {
                font-size: 17px;
            }

            QPushButton {
                font-size: 16px;
                padding: 8px 14px;
                border-radius: 8px;
                border: 1px solid #b8beca;
                background: #ffffff;
            }

            QPushButton:hover {
                background: #f0f3f8;
            }

            QPushButton:pressed {
                background: #e4e8f0;
            }

            QPushButton:disabled {
                color: #9aa3b2;
                background: #eef1f5;
                border: 1px solid #d6dbe5;
            }

            QLineEdit, QComboBox {
                font-size: 16px;
                padding: 7px;
                border-radius: 7px;
                border: 1px solid #b8beca;
                background: #ffffff;
            }

            QCheckBox {
                font-size: 17px;
                spacing: 10px;
            }

            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }

            QTableWidget {
                font-size: 14px;
            }
        """)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._previous_tab_index = -1

        self._add_tab("Состояние", lambda: StatusWidget(bg_service))
        self._add_tab("ИИ", AISettingsWidget)
        self._add_tab("Аудио", AudioSettingsWidget)
        self._add_tab("Логи", LogsWidget)
        self._add_tab("Быстрые цели", QuickTargetsWidget)
        self._add_tab("Папки", PathsWidget)
        self._add_tab("Провайдеры", ProvidersWidget)
        self._add_tab("История", HistoryWidget)
        self._add_tab("Пользовательские команды", CustomCommandsWidget)

        self.setCentralWidget(self.tabs)

        logger.info("UI | MainWindow | init_done")

    def _add_tab(self, title: str, factory):
        logger.info("UI | MainWindow | create_tab_start | %s", title)

        try:
            widget = factory()
            self.tabs.addTab(widget, title)
            logger.info("UI | MainWindow | create_tab_done | %s", title)
        except Exception as e:
            logger.exception("UI | MainWindow | create_tab_failed | %s | %s", title, e)
            raise

    def _on_tab_changed(self, index: int):
        if self._previous_tab_index >= 0 and self._previous_tab_index != index:
            previous_widget = self.tabs.widget(self._previous_tab_index)
            previous_title = self.tabs.tabText(self._previous_tab_index)

            if previous_widget and hasattr(previous_widget, "on_tab_deactivated"):
                try:
                    logger.info("UI | MainWindow | deactivate_tab | %s", previous_title)
                    previous_widget.on_tab_deactivated()
                except Exception as e:
                    logger.exception("UI | MainWindow | tab deactivation failed | %s | %s", previous_title, e)

        title = self.tabs.tabText(index) if index >= 0 else ""
        logger.info("UI | MainWindow | switch_tab | %s", title)

        widget = self.tabs.widget(index)
        if widget and hasattr(widget, "on_tab_activated"):
            try:
                widget.on_tab_activated()
            except Exception as e:
                logger.exception("UI | MainWindow | tab activation failed | %s | %s", title, e)

        self._previous_tab_index = index

    def closeEvent(self, event):
        self.hide()
        event.ignore()