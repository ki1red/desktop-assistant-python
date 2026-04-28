from PySide6.QtWidgets import QApplication

from app.windows.main_window import AssistantMainWindow
from app.windows.tray_controller import TrayController
from app.windows.background_service import BackgroundAssistantService
from app.windows.theme import apply_forced_light_theme
from app.events.notifier import AssistantNotifier
from app.settings_service import settings_service
from app.logger import get_logger


logger = get_logger("app_runtime")


class AppRuntime:
    def __init__(self):
        logger.info("AppRuntime.__init__ | start")

        logger.info("AppRuntime.__init__ | create QApplication")
        self.qt_app = QApplication([])

        # Принудительно задаём светлую тему и чёрный текст,
        # чтобы на разных устройствах Qt не подхватывал белый цвет текста.
        apply_forced_light_theme(self.qt_app)

        self.qt_app.setQuitOnLastWindowClosed(False)

        logger.info("AppRuntime.__init__ | create notifier")
        self.notifier = AssistantNotifier()

        logger.info("AppRuntime.__init__ | create BackgroundAssistantService")
        self.bg_service = BackgroundAssistantService()

        self._bg_started = False

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

        self._start_background_service_safe()
        self.tray.show()

        cfg = settings_service.get_all()
        ui = cfg.get("ui", {})
        hide_window_on_startup = bool(ui.get("hide_window_on_startup", False))

        if hide_window_on_startup:
            logger.info("AppRuntime | startup window hidden by setting")
            self.window.hide()
        else:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()

        logger.info("AppRuntime | Qt event loop start")
        return self.qt_app.exec()