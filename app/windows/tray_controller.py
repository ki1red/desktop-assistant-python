from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication


class TrayController:
    def __init__(self, window):
        self.window = window

        self.tray = QSystemTrayIcon()
        self.tray.setToolTip("Local PC Assistant")

        menu = QMenu()

        open_action = QAction("Открыть настройки")
        hide_action = QAction("Скрыть окно")
        quit_action = QAction("Выход")

        open_action.triggered.connect(self.window.showNormal)
        open_action.triggered.connect(self.window.activateWindow)
        hide_action.triggered.connect(self.window.hide)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(open_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self.window.showNormal()
                self.window.activateWindow()

    def show(self):
        self.tray.show()