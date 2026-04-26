from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.windows.logs_widget import LogsWidget
from app.windows.providers_widget import ProvidersWidget
from app.windows.quick_targets_widget import QuickTargetsWidget
from app.windows.paths_widget import PathsWidget
from app.windows.voice_widget import VoiceSettingsWidget
from app.windows.audio_widget import AudioSettingsWidget
from app.windows.history_widget import HistoryWidget
from app.windows.custom_commands_widget import CustomCommandsWidget
from app.windows.status_widget import StatusWidget
from app.windows.background_settings_widget import BackgroundSettingsWidget
from app.windows.ai_widget import AISettingsWidget
from app.logger import get_logger


logger = get_logger("ui")


class AssistantMainWindow(QMainWindow):
    def __init__(self, bg_service):
        logger.info("UI | MainWindow | init_start")

        super().__init__()
        self.setWindowTitle("Local PC Assistant")
        self.resize(1250, 860)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._add_tab("Статус", lambda: StatusWidget(bg_service))
        self._add_tab("Фоновый режим", BackgroundSettingsWidget)
        self._add_tab("AI", AISettingsWidget)
        self._add_tab("Провайдеры", ProvidersWidget)
        self._add_tab("Быстрые цели", QuickTargetsWidget)
        self._add_tab("Обязательные папки", PathsWidget)
        self._add_tab("Голос", VoiceSettingsWidget)
        self._add_tab("Запись", AudioSettingsWidget)
        self._add_tab("История", HistoryWidget)
        self._add_tab("Пользовательские команды", CustomCommandsWidget)
        self._add_tab("Логи", LogsWidget)

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
        title = self.tabs.tabText(index) if index >= 0 else ""
        logger.info("UI | MainWindow | switch_tab | %s", title)

    def closeEvent(self, event):
        self.hide()
        event.ignore()