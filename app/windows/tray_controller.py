from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication, QStyle

from app.windows.index_rebuild import rebuild_index_async


class TrayController:
    def __init__(self, window, bg_service, notifier):
        self.window = window
        self.bg_service = bg_service
        self.notifier = notifier

        self.tray = QSystemTrayIcon()

        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "tray_icon.png"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        else:
            # fallback: пусть хотя бы пустая QIcon не ломает tray
            self.tray.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        self.tray.setToolTip("Local PC Assistant")

        self.menu = QMenu()

        self.open_action = QAction("Открыть настройки")
        self.hide_action = QAction("Скрыть окно")
        self.pause_action = QAction("Пауза ассистента")
        self.rebuild_action = QAction("Перестроить индекс")
        self.quit_action = QAction("Выход")

        self.open_action.triggered.connect(self._show_window)
        self.hide_action.triggered.connect(self.window.hide)
        self.pause_action.triggered.connect(self.toggle_pause)
        self.rebuild_action.triggered.connect(self.rebuild_index)
        self.quit_action.triggered.connect(QApplication.quit)

        self.menu.addAction(self.open_action)
        self.menu.addAction(self.hide_action)
        self.menu.addAction(self.pause_action)
        self.menu.addAction(self.rebuild_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

    def _show_window(self):
        self.window.showNormal()
        self.window.activateWindow()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self._show_window()

    def toggle_pause(self):
        if self.bg_service.is_paused:
            self.bg_service.resume()
            self.pause_action.setText("Пауза ассистента")
            self.notifier.say("Ассистент возобновлён.")
        else:
            self.bg_service.pause()
            self.pause_action.setText("Возобновить ассистента")
            self.notifier.say("Ассистент поставлен на паузу.")

    def rebuild_index(self):
        rebuild_index_async(self.notifier)

    def show(self):
        self.tray.show()