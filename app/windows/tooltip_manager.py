import html
import re

from PySide6.QtCore import QObject, QEvent, QTimer, Qt, QPoint
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout


_TOOLTIP_MANAGER_INSTANCE = None


def _normalize_tooltip_text(text: str) -> str:
    text = text or ""

    # На случай, если где-то tooltip был задан HTML-строкой.
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    return text.strip()


class TooltipPopup(QFrame):
    def __init__(self):
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("CustomTooltipPopup")

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setMaximumWidth(760)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self.label)

        self.setStyleSheet("""
            QFrame#CustomTooltipPopup {
                background: #ffffff;
                border: 1px solid #c7ceda;
                border-radius: 8px;
            }

            QLabel {
                font-family: "Segoe UI";
                font-size: 10pt;
                font-weight: 400;
                font-style: normal;
                color: #1f2937;
                background: transparent;
            }
        """)

    def show_text(self, text: str, global_pos: QPoint):
        text = _normalize_tooltip_text(text)
        if not text:
            self.hide()
            return

        self.label.setText(text)

        # Для коротких подсказок не растягиваем окно слишком сильно.
        if len(text) < 90:
            self.label.setMaximumWidth(900)
        else:
            self.label.setMaximumWidth(760)

        self.adjustSize()

        x = global_pos.x() + 14
        y = global_pos.y() + 20

        screen = QApplication.screenAt(global_pos)
        if screen is None:
            screen = QApplication.primaryScreen()

        if screen is not None:
            geo = screen.availableGeometry()
            size = self.sizeHint()

            if x + size.width() > geo.right():
                x = global_pos.x() - size.width() - 14

            if y + size.height() > geo.bottom():
                y = global_pos.y() - size.height() - 14

            x = max(geo.left() + 4, x)
            y = max(geo.top() + 4, y)

        self.move(x, y)
        self.show()
        self.raise_()


class TooltipManager(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)

        self.app = app
        self.popup = TooltipPopup()

        self._pending_text = ""
        self._pending_pos = QPoint(0, 0)

        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_pending)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.popup.hide)

        self.app.installEventFilter(self)

    def eventFilter(self, obj, event):
        event_type = event.type()

        if event_type == QEvent.Type.ToolTip:
            text = ""

            try:
                text = obj.toolTip()
            except Exception:
                text = ""

            text = _normalize_tooltip_text(text)

            if not text:
                self.popup.hide()
                event.accept()
                return True

            try:
                global_pos = event.globalPos()
            except Exception:
                global_pos = QPoint(0, 0)

            self._pending_text = text
            self._pending_pos = global_pos

            # Тут ставим небольшую задержку уже для нашего popup.
            # Сам QEvent.ToolTip приходит после системной задержки, которую мы уменьшаем в main_window.py.
            self._show_timer.start(30)

            event.accept()
            return True

        if event_type in (
            QEvent.Type.Leave,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.Wheel,
            QEvent.Type.FocusOut,
            QEvent.Type.WindowDeactivate,
        ):
            self._show_timer.stop()
            self.popup.hide()

        return False

    def _show_pending(self):
        self.popup.show_text(self._pending_text, self._pending_pos)

        # Если пользователь оставил мышь на месте, подсказка не должна висеть бесконечно.
        self._hide_timer.start(9000)


def install_custom_tooltips(app: QApplication):
    global _TOOLTIP_MANAGER_INSTANCE

    if _TOOLTIP_MANAGER_INSTANCE is None:
        _TOOLTIP_MANAGER_INSTANCE = TooltipManager(app)

    return _TOOLTIP_MANAGER_INSTANCE