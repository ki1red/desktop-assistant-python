from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout


STATUS_COLORS = {
    "ok": ("#e7f6ec", "#16723a"),
    "process": ("#fff3d6", "#8a5a00"),
    "bad": ("#fde8e8", "#9b1c1c"),
    "neutral": ("#eef1f6", "#303846"),
}


def make_page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("font-size: 34px; font-weight: 600;")
    return label


def make_status_badge(text: str = "XXX", min_width: int = 170) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setMinimumWidth(min_width)
    apply_status_style(label, "neutral")
    return label


def apply_status_style(label: QLabel, status_kind: str):
    bg, fg = STATUS_COLORS.get(status_kind, STATUS_COLORS["neutral"])

    label.setStyleSheet(f"""
        QLabel {{
            font-size: 25px;
            font-weight: 700;
            padding: 8px 16px;
            border-radius: 12px;
            background: {bg};
            color: {fg};
        }}
    """)


class InfoCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("InfoCard")
        self.setStyleSheet("""
            QFrame#InfoCard {
                background: #ffffff;
                border: 1px solid #dde2ea;
                border-radius: 14px;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(14)