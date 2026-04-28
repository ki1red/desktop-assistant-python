from pathlib import Path
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPixmap, QPainter, QPen
from PySide6.QtWidgets import QApplication


def _ensure_checkbox_checkmark_image() -> str:
    """
    Создаёт маленькую PNG-галочку для QCheckBox.

    Qt StyleSheet не умеет нормально рисовать галочку через CSS,
    поэтому создаём картинку программно и подключаем её через image: url(...).
    """
    theme_dir = Path(tempfile.gettempdir()) / "LocalAssistantTheme"
    theme_dir.mkdir(parents=True, exist_ok=True)

    image_path = theme_dir / "checkbox_check.png"

    if image_path.exists():
        return image_path.as_posix()

    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    pen = QPen(QColor("#FFFFFF"))
    pen.setWidth(3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(pen)
    painter.drawLine(4, 8, 7, 11)
    painter.drawLine(7, 11, 12, 4)
    painter.end()

    pixmap.save(str(image_path), "PNG")

    return image_path.as_posix()


def _build_forced_light_qss() -> str:
    checkmark_url = _ensure_checkbox_checkmark_image()

    return f"""
QWidget {{
    color: #111111;
}}

/* Основные окна и крупные контейнеры */
QMainWindow,
QDialog {{
    background-color: #F7F7F7;
}}

QTabWidget::pane {{
    background-color: #F7F7F7;
    border-top: 1px solid #D0D0D0;
}}

QScrollArea {{
    background-color: #F7F7F7;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: #F7F7F7;
}}

/* Текстовые элементы без собственного фона */
QLabel,
QCheckBox,
QRadioButton,
QStatusBar {{
    color: #111111;
    background-color: transparent;
}}

/* Чекбоксы */
QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #707070;
    border-radius: 4px;
    background-color: #FFFFFF;
}}

QCheckBox::indicator:hover {{
    border: 1px solid #2D6CDF;
    background-color: #F8FBFF;
}}

QCheckBox::indicator:unchecked {{
    border: 1px solid #707070;
    background-color: #FFFFFF;
}}

QCheckBox::indicator:checked {{
    border: 1px solid #1F56B5;
    background-color: #2D6CDF;
    image: url("{checkmark_url}");
}}

QCheckBox::indicator:disabled {{
    border: 1px solid #B0B0B0;
    background-color: #E8E8E8;
}}

QCheckBox::indicator:checked:disabled {{
    border: 1px solid #999999;
    background-color: #B8B8B8;
    image: url("{checkmark_url}");
}}

/* Радиокнопки */
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #707070;
    border-radius: 8px;
    background-color: #FFFFFF;
}}

QRadioButton::indicator:checked {{
    border: 1px solid #1F56B5;
    background-color: #2D6CDF;
}}

/* Группы */
QGroupBox {{
    color: #111111;
    border: 1px solid #D0D0D0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    background-color: #FFFFFF;
}}

QGroupBox::title {{
    color: #111111;
    background-color: transparent;
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}

/* Поля ввода */
QLineEdit,
QTextEdit,
QPlainTextEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox,
QListWidget,
QTableWidget,
QTreeWidget {{
    color: #111111;
    background-color: #FFFFFF;
    selection-color: #FFFFFF;
    selection-background-color: #2D6CDF;
    border: 1px solid #CFCFCF;
    border-radius: 6px;
    padding: 4px;
}}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus {{
    border: 1px solid #2D6CDF;
}}

/* Кнопки */
QPushButton {{
    color: #111111;
    background-color: #EFEFEF;
    border: 1px solid #C8C8C8;
    border-radius: 7px;
    padding: 6px 10px;
}}

QPushButton:hover {{
    background-color: #E2E2E2;
}}

QPushButton:pressed {{
    background-color: #D6D6D6;
}}

QPushButton:disabled,
QLabel:disabled,
QCheckBox:disabled,
QRadioButton:disabled {{
    color: #777777;
}}

/* Вкладки */
QTabBar {{
    background-color: #F7F7F7;
}}

QTabBar::tab {{
    color: #111111;
    background-color: #EAEAEA;
    padding: 8px 14px;
    border: 1px solid #CFCFCF;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    color: #111111;
    background-color: #FFFFFF;
}}

QTabBar::tab:hover {{
    background-color: #F3F3F3;
}}

/* Меню */
QMenu,
QMenuBar {{
    color: #111111;
    background-color: #FFFFFF;
}}

QMenu::item:selected {{
    color: #FFFFFF;
    background-color: #2D6CDF;
}}

/* Подсказки */
QToolTip {{
    color: #111111;
    background-color: #FFFFDD;
    border: 1px solid #C8C8A0;
}}

/* Скролл */
QScrollBar {{
    background-color: #F0F0F0;
}}

/* Таблицы */
QHeaderView::section {{
    color: #111111;
    background-color: #EFEFEF;
    border: 1px solid #D0D0D0;
    padding: 4px;
}}
"""


def apply_forced_light_theme(app: QApplication) -> None:
    """
    Принудительно задаёт светлую палитру и чёрный текст.

    Важно:
    не задаём background-color глобально для QWidget,
    иначе QLabel внутри карточек становятся серыми прямоугольниками.
    """
    app.setStyle("Fusion")

    palette = QPalette()

    palette.setColor(QPalette.ColorRole.Window, QColor("#F7F7F7"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#111111"))

    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F0F0F0"))

    palette.setColor(QPalette.ColorRole.Text, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#EFEFEF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111111"))

    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFDD"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#111111"))

    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#777777"))

    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2D6CDF"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))

    app.setPalette(palette)
    app.setStyleSheet(_build_forced_light_qss())