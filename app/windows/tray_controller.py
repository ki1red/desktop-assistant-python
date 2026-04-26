from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication, QStyle, QMessageBox

from app.windows.index_rebuild import rebuild_index_async
from app.logger import get_logger


logger = get_logger("tray")


class TrayController:
    def __init__(self, window, bg_service, notifier):
        logger.info("TrayController | init_start")

        self.window = window
        self.bg_service = bg_service
        self.notifier = notifier

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("TrayController | system tray is not available")
            QMessageBox.warning(
                self.window,
                "Трей недоступен",
                "Системный трей сейчас недоступен. Окно приложения будет открыто обычным способом."
            )

        # Передаём parent, чтобы Qt точно держал объект живым.
        self.tray = QSystemTrayIcon(self.window)

        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "tray_icon.png"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
            logger.info("TrayController | icon loaded: %s", icon_path)
        else:
            self.tray.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
            logger.warning("TrayController | tray icon not found, fallback icon used: %s", icon_path)

        self.tray.setToolTip("Local PC Assistant")

        self.menu = QMenu(self.window)

        self.open_action = QAction("Открыть настройки", self.window)
        self.hide_action = QAction("Скрыть окно", self.window)
        self.pause_action = QAction("Пауза ассистента", self.window)
        self.rebuild_action = QAction("Перестроить индекс", self.window)
        self.quit_action = QAction("Выход", self.window)

        self.open_action.triggered.connect(self._show_window)
        self.hide_action.triggered.connect(self._hide_window)
        self.pause_action.triggered.connect(self.toggle_pause)
        self.rebuild_action.triggered.connect(self.rebuild_index)
        self.quit_action.triggered.connect(self._quit_app)

        self.menu.addAction(self.open_action)
        self.menu.addAction(self.hide_action)
        self.menu.addAction(self.pause_action)
        self.menu.addAction(self.rebuild_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

        logger.info("TrayController | init_done")

    def _show_window(self):
        logger.info("TrayController | show_window")

        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _hide_window(self):
        logger.info("TrayController | hide_window")
        self.window.hide()

    def _toggle_window(self):
        if self.window.isVisible():
            logger.info("TrayController | toggle_window | hide")
            self.window.hide()
        else:
            logger.info("TrayController | toggle_window | show")
            self._show_window()

    def _on_activated(self, reason):
        logger.info("TrayController | activated | reason=%s", reason)

        # На Windows поведение может отличаться:
        # где-то приходит Trigger, где-то DoubleClick.
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        ):
            self._toggle_window()

    def toggle_pause(self):
        logger.info("TrayController | toggle_pause")

        if self.bg_service.is_paused:
            self.bg_service.resume()
            self.pause_action.setText("Пауза ассистента")
            self.notifier.say("Ассистент возобновлён.")
        else:
            self.bg_service.pause()
            self.pause_action.setText("Возобновить ассистента")
            self.notifier.say("Ассистент поставлен на паузу.")

    def rebuild_index(self):
        logger.info("TrayController | rebuild_index")
        rebuild_index_async(self.notifier)

    def _quit_app(self):
        logger.info("TrayController | quit_app")

        try:
            self.bg_service.stop()
        except Exception as e:
            logger.exception("TrayController | error while stopping background service: %s", e)

        QApplication.quit()

    def show(self):
        logger.info("TrayController | show")

        self.tray.show()

        if self.tray.isVisible():
            logger.info("TrayController | tray is visible")
        else:
            logger.warning("TrayController | tray is not visible after show()")

        self.tray.showMessage(
            "Local PC Assistant",
            "Ассистент запущен. Нажмите на значок, чтобы открыть настройки.",
            QSystemTrayIcon.MessageIcon.Information,
            2500
        )