from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QGridLayout,
    QFrame,
)

from app.dictation.state import dictation_state
from app.chat.state import chat_state
from app.events.notifier import AssistantNotifier
from app.indexing.index_state import index_state
from app.settings_service import settings_service
from app.speech.recorder import list_input_devices


def _mode_text() -> str:
    if chat_state.is_enabled():
        return "общение"
    if dictation_state.is_enabled():
        return "диктовка"
    return "обычный"


def _mode_tooltip() -> str:
    if chat_state.is_enabled():
        return "Режим общения отправляет ваши фразы в ИИ и ждёт текстовый ответ."
    if dictation_state.is_enabled():
        return "Режим диктовки вставляет распознанную речь как текст в активное окно."
    return "Обычный режим распознаёт голосовую команду и выполняет действие на компьютере."


def _make_page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet("font-size: 34px; font-weight: 600;")
    return label


def _make_status_badge() -> QLabel:
    label = QLabel("XXX")
    label.setAlignment(Qt.AlignCenter)
    label.setMinimumWidth(170)
    return label


def _apply_status_style(label: QLabel, status_kind: str):
    if status_kind == "ok":
        bg, fg = "#e7f6ec", "#16723a"
    elif status_kind == "process":
        bg, fg = "#fff3d6", "#8a5a00"
    else:
        bg, fg = "#fde8e8", "#9b1c1c"

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


class StatusRow(QFrame):
    def __init__(self, title: str, value: str = "", tooltip: str = ""):
        super().__init__()
        self.setObjectName("StatusRow")
        self.setStyleSheet("""
            QFrame#StatusRow {
                background: #ffffff;
                border: 1px solid #dde2ea;
                border-radius: 14px;
            }
        """)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 21px; font-weight: 500;")

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 21px; font-weight: 600;")
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.value_label, 1)

        if tooltip:
            self.set_tooltip(tooltip)

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_tooltip(self, tooltip: str):
        self.setToolTip(tooltip)
        self.title_label.setToolTip(tooltip)
        self.value_label.setToolTip(tooltip)


class StatusWidget(QWidget):
    def __init__(self, bg_service):
        super().__init__()
        self.bg_service = bg_service
        self.notifier = AssistantNotifier()
        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(26)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        self.title_label = _make_page_title("Состояние")
        self.overall_status = _make_status_badge()

        header.addWidget(self.title_label, 0, 1)
        header.addWidget(self.overall_status, 0, 2, alignment=Qt.AlignRight | Qt.AlignVCenter)

        root.addLayout(header)

        self.command_row = StatusRow(
            "Обработка команд",
            tooltip="Показывает, готов ли ассистент принимать голосовые команды по горячей клавише."
        )

        self.mic_row = StatusRow(
            "Микрофон",
            tooltip="Если микрофон не выбран, перейдите на вкладку «Аудио» и выберите устройство ввода."
        )

        self.mode_row = StatusRow(
            "Режим",
            tooltip="Обычный режим выполняет команды, диктовка вводит текст, режим общения отправляет фразы в ИИ."
        )

        self.index_row = StatusRow(
            "Индексация файлов",
            tooltip="Индекс нужен, чтобы ассистент быстро находил приложения, файлы и папки на компьютере."
        )

        rows_layout = QGridLayout()
        rows_layout.setHorizontalSpacing(28)
        rows_layout.setVerticalSpacing(22)

        rows_layout.addWidget(self.command_row, 0, 0)
        rows_layout.addWidget(self.index_row, 0, 1)
        rows_layout.addWidget(self.mic_row, 1, 0)
        rows_layout.addWidget(self.mode_row, 2, 0)

        root.addLayout(rows_layout)

        root.addStretch(1)

        self.actions_row = QHBoxLayout()
        self.actions_row.addStretch(1)

        self.test_voice_btn = QPushButton("Проверить голос")
        self.refresh_btn = QPushButton("Обновить")

        self.test_voice_btn.clicked.connect(self.test_voice)
        self.refresh_btn.clicked.connect(self.refresh)

        self.actions_row.addWidget(self.test_voice_btn)
        self.actions_row.addWidget(self.refresh_btn)

        # Пока скрываем, но не удаляем: могут пригодиться для диагностики.
        self.test_voice_btn.setVisible(False)
        self.refresh_btn.setVisible(False)

        root.addLayout(self.actions_row)

        self.refresh()

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    def on_tab_activated(self):
        self.refresh()

    def _get_mic_state(self) -> tuple[str, str, bool]:
        cfg = settings_service.get_all()
        audio = cfg.get("audio", {})

        mic_enabled = bool(audio.get("microphone_enabled", True))
        mic_name = audio.get("input_device_name", "").strip()

        if not mic_enabled:
            return (
                "выключен",
                "Использование микрофона запрещено во вкладке «Аудио». Без микрофона ассистент не сможет принимать голосовые команды.",
                False,
            )

        if not mic_name:
            return (
                "не выбран",
                "Микрофон не выбран. Перейдите на вкладку «Аудио» и выберите устройство ввода.",
                False,
            )

        try:
            devices = list_input_devices()
            exists = any(dev["name"] == mic_name for dev in devices)
        except Exception as e:
            return (
                "не проверен",
                f"Не удалось получить список микрофонов: {e}",
                False,
            )

        if not exists:
            return (
                "недоступен",
                "Выбранный микрофон сейчас недоступен. Проверьте подключение или выберите другое устройство во вкладке «Аудио».",
                False,
            )

        return (
            "работает",
            "Микрофон выбран и найден среди доступных устройств записи.",
            True,
        )

    def _compute_overall_status(self, index_running: bool, mic_ok: bool) -> tuple[str, str, str]:
        if index_running:
            return (
                "Настраивается",
                "process",
                "Ассистент запускается нормально, но сейчас выполняется индексация файлов."
            )

        if self.bg_service.is_paused:
            return (
                "На паузе",
                "bad",
                "Ассистент поставлен на паузу. Команды по горячей клавише временно не выполняются."
            )

        if not mic_ok:
            return (
                "Не работает",
                "bad",
                "Ассистент запущен, но не может принимать голосовые команды без доступного микрофона."
            )

        return (
            "Активно",
            "ok",
            "Ассистент готов принимать голосовые команды."
        )

    def refresh(self):
        index = index_state.snapshot()
        index_running = bool(index.get("is_running", False))
        index_count = index.get("indexed_count", 0)
        index_message = index.get("message", "")

        mic_value, mic_tooltip, mic_ok = self._get_mic_state()

        overall_text, overall_kind, overall_tip = self._compute_overall_status(index_running, mic_ok)
        self.overall_status.setText(overall_text)
        self.overall_status.setToolTip(overall_tip)
        _apply_status_style(self.overall_status, overall_kind)

        if self.bg_service.is_busy():
            command_value = "выполняется"
            command_tip = "Ассистент сейчас обрабатывает команду. Повторное нажатие горячей клавиши может отменить операцию."
        elif self.bg_service.is_paused:
            command_value = "на паузе"
            command_tip = "Ассистент временно не принимает команды, потому что он поставлен на паузу."
        elif not mic_ok:
            command_value = "недоступно"
            command_tip = "Команды недоступны, потому что микрофон не работает, не выбран или выключен."
        else:
            command_value = "доступно"
            command_tip = f"Ассистент готов принимать команды. Горячая клавиша: {self.bg_service.hotkey}"

        self.command_row.set_value(command_value)
        self.command_row.set_tooltip(command_tip)

        self.mic_row.set_value(mic_value)
        self.mic_row.set_tooltip(mic_tooltip)

        self.mode_row.set_value(_mode_text())
        self.mode_row.set_tooltip(_mode_tooltip())

        if index_running:
            index_value = "выполняется"
            index_tip = f"Сейчас выполняется индексация файлов. {index_message}"
        else:
            index_value = "выполнено"
            index_tip = f"Индекс готов. Объектов в индексе: {index_count}. Индекс нужен для быстрого поиска файлов, папок и приложений."

        self.index_row.set_value(index_value)
        self.index_row.set_tooltip(index_tip)

    def test_voice(self):
        self.notifier.say("Проверка голоса. Ассистент работает.")