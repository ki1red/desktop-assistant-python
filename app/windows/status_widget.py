from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

from app.runtime_control import runtime_control
from app.dictation.state import dictation_state
from app.chat.state import chat_state
from app.events.notifier import AssistantNotifier


class StatusWidget(QWidget):
    def __init__(self, bg_service):
        super().__init__()
        self.bg_service = bg_service
        self.notifier = AssistantNotifier()
        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.hotkey_label = QLabel()
        self.busy_label = QLabel()
        self.paused_label = QLabel()
        self.dictation_label = QLabel()
        self.chat_label = QLabel()

        layout.addWidget(QLabel("Текущее состояние ассистента:"))
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.paused_label)
        layout.addWidget(self.dictation_label)
        layout.addWidget(self.chat_label)

        row = QHBoxLayout()
        self.test_voice_btn = QPushButton("Тест голоса")
        self.refresh_btn = QPushButton("Обновить")
        row.addWidget(self.test_voice_btn)
        row.addWidget(self.refresh_btn)

        self.test_voice_btn.clicked.connect(self.test_voice)
        self.refresh_btn.clicked.connect(self.refresh)

        layout.addLayout(row)

        self.refresh()

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    def refresh(self):
        self.hotkey_label.setText(f"Горячая клавиша: {self.bg_service.hotkey}")
        self.busy_label.setText(f"Выполняет команду: {'Да' if runtime_control.is_busy() else 'Нет'}")
        self.paused_label.setText(f"Ассистент на паузе: {'Да' if self.bg_service.is_paused else 'Нет'}")
        self.dictation_label.setText(f"Диктовка включена: {'Да' if dictation_state.is_enabled() else 'Нет'}")
        self.chat_label.setText(f"Режим общения включён: {'Да' if chat_state.is_enabled() else 'Нет'}")

    def test_voice(self):
        self.notifier.say("Проверка голоса. Ассистент работает.")