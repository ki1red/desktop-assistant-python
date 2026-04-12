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


class AssistantMainWindow(QMainWindow):
    def __init__(self, bg_service):
        super().__init__()
        self.setWindowTitle("Local PC Assistant")
        self.resize(1250, 860)

        tabs = QTabWidget()
        tabs.addTab(StatusWidget(bg_service), "Статус")
        tabs.addTab(BackgroundSettingsWidget(), "Фоновый режим")
        tabs.addTab(AISettingsWidget(), "AI")
        tabs.addTab(ProvidersWidget(), "Провайдеры")
        tabs.addTab(QuickTargetsWidget(), "Быстрые цели")
        tabs.addTab(PathsWidget(), "Обязательные папки")
        tabs.addTab(VoiceSettingsWidget(), "Голос")
        tabs.addTab(AudioSettingsWidget(), "Запись")
        tabs.addTab(HistoryWidget(), "История")
        tabs.addTab(CustomCommandsWidget(), "Пользовательские команды")
        tabs.addTab(LogsWidget(), "Логи")

        self.setCentralWidget(tabs)

    def closeEvent(self, event):
        self.hide()
        event.ignore()