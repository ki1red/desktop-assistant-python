from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.windows.logs_widget import LogsWidget
from app.windows.providers_widget import ProvidersWidget
from app.windows.quick_targets_widget import QuickTargetsWidget
from app.windows.paths_widget import PathsWidget
from app.windows.voice_widget import VoiceSettingsWidget
from app.windows.history_widget import HistoryWidget
from app.windows.custom_commands_widget import CustomCommandsWidget


class AssistantMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local PC Assistant")
        self.resize(1200, 780)

        tabs = QTabWidget()
        tabs.addTab(ProvidersWidget(), "Провайдеры")
        tabs.addTab(QuickTargetsWidget(), "Быстрые цели")
        tabs.addTab(PathsWidget(), "Обязательные папки")
        tabs.addTab(VoiceSettingsWidget(), "Голос")
        tabs.addTab(HistoryWidget(), "История")
        tabs.addTab(CustomCommandsWidget(), "Пользовательские команды")
        tabs.addTab(LogsWidget(), "Логи")

        self.setCentralWidget(tabs)

    def closeEvent(self, event):
        self.hide()
        event.ignore()