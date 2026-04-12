from PySide6.QtWidgets import QApplication

from app.windows.main_window import AssistantMainWindow
from app.windows.tray_controller import TrayController
from app.windows.background_service import BackgroundAssistantService
from app.events.notifier import AssistantNotifier
from app.logger import get_logger


logger = get_logger("app_runtime")


class AppRuntime:
    def __init__(self):
        self.qt_app = QApplication([])
        self.bg_service = BackgroundAssistantService()
        self.window = AssistantMainWindow(self.bg_service)
        self.notifier = AssistantNotifier()
        self.tray = TrayController(self.window, self.bg_service, self.notifier)

    def start(self):
        logger.info("Запуск AppRuntime.")
        self.bg_service.start()
        self.window.hide()
        self.tray.show()
        return self.qt_app.exec()