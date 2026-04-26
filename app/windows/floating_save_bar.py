from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QSizePolicy,
)


class FloatingSaveBar(QFrame):
    clicked = Signal()

    def __init__(self, parent=None, button_text: str = "Сохранить изменения"):
        super().__init__(parent)

        self._mode = "hidden"
        self._button_text = button_text

        self.setObjectName("FloatingSaveBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(76)
        self.hide()

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(22, 12, 22, 12)
        self.layout.setSpacing(18)

        self.label = QLabel("Есть несохранённые изменения")
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.button = QPushButton(button_text)
        self.button.clicked.connect(self.clicked.emit)

        # Важно:
        # label занимает всё свободное место.
        # Поэтому в saved-режиме, когда кнопка скрыта, текст реально центрируется
        # по всей всплывающей панели, а не по маленькому QLabel слева.
        self.layout.addWidget(self.label, 1)
        self.layout.addWidget(self.button, 0)

        self._apply_dirty_style()

    def _apply_dirty_style(self):
        self.setStyleSheet("""
            QFrame#FloatingSaveBar {
                background: #ffffff;
                border: 1px solid #cfd6e2;
                border-radius: 18px;
            }

            QLabel {
                font-size: 17px;
                font-weight: 500;
                color: #303846;
            }

            QPushButton {
                font-size: 19px;
                font-weight: 700;
                padding: 12px 28px;
                border-radius: 14px;
                border: 1px solid #16723a;
                background: #1f8f4d;
                color: white;
            }

            QPushButton:hover {
                background: #187a40;
            }

            QPushButton:pressed {
                background: #136833;
            }
        """)

    def _apply_saved_style(self):
        self.setStyleSheet("""
            QFrame#FloatingSaveBar {
                background: #e7f6ec;
                border: 1px solid #99d4ad;
                border-radius: 18px;
            }

            QLabel {
                font-size: 26px;
                font-weight: 800;
                color: #16723a;
            }

            QPushButton {
                font-size: 19px;
                font-weight: 700;
                padding: 12px 28px;
                border-radius: 14px;
                border: 1px solid #16723a;
                background: #1f8f4d;
                color: white;
            }
        """)

    def _beep_success(self):
        try:
            QApplication.beep()
        except Exception:
            pass

    def set_dirty(self, dirty: bool):
        if dirty:
            self._mode = "dirty"
            self._apply_dirty_style()

            self.layout.setContentsMargins(22, 12, 22, 12)

            self.label.setText("Есть несохранённые изменения")
            self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            self.button.setText(self._button_text)
            self.button.setVisible(True)

            self.setVisible(True)
            self.reposition()
            self.raise_()
        else:
            if self._mode != "saved":
                self._mode = "hidden"
                self.hide()

    def show_saved(self, message: str = "Сохранено!"):
        self._mode = "saved"

        self._apply_saved_style()

        self.layout.setContentsMargins(0, 12, 0, 12)

        self.button.setVisible(False)

        self.label.setText(message)
        self.label.setAlignment(Qt.AlignCenter)

        self.setVisible(True)
        self.reposition()
        self.raise_()

        self._beep_success()

        QTimer.singleShot(1300, self._hide_if_still_saved)

    def _hide_if_still_saved(self):
        if self._mode == "saved":
            self._mode = "hidden"
            self.hide()

    def reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return

        parent_width = parent.width()
        parent_height = parent.height()

        width = min(max(520, int(parent_width * 0.52)), 760)
        self.setFixedWidth(width)

        x = max(16, (parent_width - width) // 2)
        y = max(16, parent_height - self.height() - 28)

        self.move(x, y)
        self.raise_()