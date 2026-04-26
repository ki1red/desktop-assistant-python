from PySide6.QtWidgets import QApplication

from app.windows.main_window import AssistantMainWindow
from app.windows.tray_controller import TrayController
from app.windows.background_service import BackgroundAssistantService
from app.events.notifier import AssistantNotifier
from app.logger import get_logger


logger = get_logger("app_runtime")


class AppRuntime:
    def __init__(self):
        logger.info("AppRuntime.__init__ | start")

        logger.info("AppRuntime.__init__ | create QApplication")
        self.qt_app = QApplication([])

        # Важно для tray-приложений:
        # если окно скрыто или закрыто крестиком, приложение не должно завершаться.
        self.qt_app.setQuitOnLastWindowClosed(False)

        logger.info("AppRuntime.__init__ | create notifier")
        self.notifier = AssistantNotifier()

        logger.info("AppRuntime.__init__ | create BackgroundAssistantService")
        self.bg_service = BackgroundAssistantService()

        self._bg_started = False

        # Фоновый listener запускаем до создания тяжёлого UI.
        # Благодаря ленивому созданию pipeline этот этап теперь не должен грузить Whisper.
        logger.info("AppRuntime.__init__ | start background service before UI")
        self._start_background_service_safe()

        logger.info("AppRuntime.__init__ | create MainWindow")
        self.window = AssistantMainWindow(self.bg_service)

        logger.info("AppRuntime.__init__ | create TrayController")
        self.tray = TrayController(self.window, self.bg_service, self.notifier)

        logger.info("AppRuntime.__init__ | done")

    def _start_background_service_safe(self):
        if self._bg_started:
            return

        try:
            self.bg_service.start()
            self._bg_started = True
            logger.info("AppRuntime | background service started")
        except Exception as e:
            logger.exception("AppRuntime | background service start failed: %s", e)

    def start(self):
        logger.info("Запуск AppRuntime.")

        # На всякий случай повторно проверяем, что фоновый сервис запущен.
        self._start_background_service_safe()

        self.tray.show()

        # Пока НЕ скрываем приложение в трей при запуске.
        # Окно должно открываться сразу, чтобы пользователь не терял доступ к настройкам.
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

        logger.info("AppRuntime | Qt event loop start")
        return self.qt_app.exec()