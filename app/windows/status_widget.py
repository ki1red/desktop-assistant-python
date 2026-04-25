from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QProgressBar
)

from app.dictation.state import dictation_state
from app.chat.state import chat_state
from app.events.notifier import AssistantNotifier
from app.indexing.index_state import index_state
from app.settings_service import settings_service


def _yn(flag: bool) -> str:
    return "включён" if flag else "выключен"


class StatusWidget(QWidget):
    def __init__(self, bg_service):
        super().__init__()
        self.bg_service = bg_service
        self.notifier = AssistantNotifier()
        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("<b>Сводка состояния ассистента</b>")
        layout.addWidget(title)

        self.hotkey_label = QLabel()
        self.busy_label = QLabel()
        self.paused_label = QLabel()
        self.dictation_label = QLabel()
        self.chat_label = QLabel()
        self.mic_label = QLabel()
        self.output_label = QLabel()
        self.gain_label = QLabel()

        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.busy_label)
        layout.addWidget(self.paused_label)
        layout.addWidget(self.dictation_label)
        layout.addWidget(self.chat_label)
        layout.addWidget(self.mic_label)
        layout.addWidget(self.output_label)
        layout.addWidget(self.gain_label)

        layout.addSpacing(12)

        index_title = QLabel("<b>Состояние индекса</b>")
        layout.addWidget(index_title)

        self.index_label = QLabel()
        self.index_message_label = QLabel()
        self.index_count_label = QLabel()
        self.index_progress = QProgressBar()
        self.index_progress.setVisible(False)

        layout.addWidget(self.index_label)
        layout.addWidget(self.index_message_label)
        layout.addWidget(self.index_count_label)
        layout.addWidget(self.index_progress)

        row = QHBoxLayout()
        self.test_voice_btn = QPushButton("Проверить голос")
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
        cfg = settings_service.get_all()
        mic_name = cfg.get("audio", {}).get("input_device_name", "").strip()
        output_name = cfg.get("audio", {}).get("output_device_name", "").strip()
        input_gain = cfg.get("audio", {}).get("input_gain", 1.0)

        self.hotkey_label.setText(f"<b>Горячая клавиша:</b> {self.bg_service.hotkey}")
        self.busy_label.setText(
            f"<b>Обработка команды:</b> {'выполняется' if self.bg_service.is_busy() else 'ожидание'}"
        )
        self.paused_label.setText(f"<b>Фоновый режим:</b> {'на паузе' if self.bg_service.is_paused else 'активен'}")
        self.dictation_label.setText(f"<b>Режим диктовки:</b> {_yn(dictation_state.is_enabled())}")
        self.chat_label.setText(f"<b>Режим общения:</b> {_yn(chat_state.is_enabled())}")
        self.mic_label.setText(f"<b>Выбранный микрофон:</b> {mic_name if mic_name else 'не выбран'}")
        self.output_label.setText(f"<b>Устройство вывода:</b> {output_name if output_name else 'не выбрано'}")
        self.gain_label.setText(f"<b>Усиление микрофона:</b> {input_gain}")

        state = index_state.snapshot()
        self.index_label.setText(
            f"<b>Индексация:</b> {'выполняется' if state['is_running'] else 'не выполняется'}"
        )
        self.index_message_label.setText(state["message"])
        self.index_count_label.setText(f"<b>Объектов в индексе:</b> {state['indexed_count']}")

        if state["is_running"]:
            self.index_progress.setVisible(True)
            self.index_progress.setRange(0, 0)
        else:
            self.index_progress.setVisible(False)

    def test_voice(self):
        self.notifier.say("Проверка голоса. Ассистент работает.")