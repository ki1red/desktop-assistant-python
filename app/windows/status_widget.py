import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QApplication,
)

from app.dictation.state import dictation_state
from app.chat.state import chat_state
from app.events.notifier import AssistantNotifier
from app.indexing.index_state import index_state
from app.settings_service import settings_service
from app.speech.recorder import list_input_devices
from app.windows.ui_kit import make_page_title, make_status_badge, apply_status_style
from app.indexing.indexer import get_index_count
from app.indexing.db import get_index_metadata


SUPPORTED_RUNTIME_AI_PROVIDERS = {"stub", "ollama"}


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
        self._cached_index_count = 0
        self._index_count_tick = 0
        self._last_recovery_attempt = 0.0
        self._build_ui()
        self._start_timer()

    def _get_persistent_index_count(self, force: bool = False) -> int:
        self._index_count_tick += 1

        if not force and self._cached_index_count > 0 and self._index_count_tick < 10:
            return self._cached_index_count

        self._index_count_tick = 0

        try:
            self._cached_index_count = int(get_index_count())
        except Exception:
            self._cached_index_count = 0

        return self._cached_index_count

    def _maybe_recover_missing_index(self, index_count: int, index_running: bool, index_status: str):
        if index_running:
            return

        if index_count > 0:
            return

        now = time.monotonic()
        if now - self._last_recovery_attempt < 10:
            return

        self._last_recovery_attempt = now

        try:
            from app.bootstrap import ensure_initial_index

            ensure_initial_index(reason="status_widget_recovery")
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(26)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        self.title_label = make_page_title("Состояние")
        self.overall_status = make_status_badge()

        header.addWidget(self.title_label, 0, 1)
        header.addWidget(
            self.overall_status,
            0,
            2,
            alignment=Qt.AlignRight | Qt.AlignVCenter,
        )

        root.addLayout(header)

        self.command_row = StatusRow(
            "Обработка команд",
            tooltip="Показывает, готов ли ассистент принимать голосовые команды."
        )

        self.mic_row = StatusRow(
            "Микрофон",
            tooltip="Если микрофон не выбран, перейдите на вкладку «Аудио» и выберите устройство ввода."
        )

        self.mode_row = StatusRow(
            "Режим",
            tooltip="Обычный режим выполняет команды, диктовка вводит текст, режим общения отправляет фразы в ИИ."
        )

        self.ai_row = StatusRow(
            "Искусственный интеллект",
            tooltip="ИИ помогает уточнять команды после распознавания речи, но ассистент может работать и без него."
        )

        self.activation_row = StatusRow(
            "Тип активации",
            tooltip="Способ активации определяет, как ассистент начинает слушать команду: по горячей клавише или после голосового обращения. Настраивается во вкладке «Ассистент»."
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
        rows_layout.addWidget(self.ai_row, 3, 0)
        rows_layout.addWidget(self.activation_row, 4, 0)

        root.addLayout(rows_layout)
        root.addStretch(1)

        self.actions_row = QHBoxLayout()
        self.actions_row.addStretch(1)

        self.hide_btn = QPushButton("Скрыть ассистента")
        self.hide_btn.setToolTip("Скрывает окно приложения. Ассистент продолжит работать в фоне.")
        self.hide_btn.clicked.connect(self.hide_assistant)

        self.quit_btn = QPushButton("Выключить ассистента")
        self.quit_btn.setToolTip("Полностью закрывает приложение и останавливает фоновый сервис.")
        self.quit_btn.clicked.connect(self.quit_assistant)
        self.quit_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 8px 14px;
                border-radius: 8px;
                border: 1px solid #b91c1c;
                background: #fee2e2;
                color: #991b1b;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #fecaca;
            }

            QPushButton:pressed {
                background: #fca5a5;
            }
        """)

        self.test_voice_btn = QPushButton("Проверить голос")
        self.refresh_btn = QPushButton("Обновить")

        self.test_voice_btn.clicked.connect(self.test_voice)
        self.refresh_btn.clicked.connect(self.refresh)

        self.test_voice_btn.setVisible(False)
        self.refresh_btn.setVisible(False)

        self.actions_row.addWidget(self.test_voice_btn)
        self.actions_row.addWidget(self.refresh_btn)
        self.actions_row.addWidget(self.hide_btn)
        self.actions_row.addWidget(self.quit_btn)

        root.addLayout(self.actions_row)

        self.refresh()

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    def on_tab_activated(self):
        self._get_persistent_index_count(force=True)
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

    def _get_ai_state(self) -> tuple[str, str]:
        cfg = settings_service.get_all()
        ai = cfg.get("ai", {})

        enabled = bool(ai.get("enabled", True))
        apply_to_all = bool(ai.get("apply_to_all_commands", True))
        provider = (ai.get("provider", "") or "").strip()

        ollama_host = (ai.get("ollama_host", "") or "").strip()
        ollama_model = (ai.get("ollama_model", "") or "").strip()

        provider_endpoint = (ai.get("provider_endpoint", "") or "").strip()
        remote_model = (ai.get("remote_model", "") or "").strip()

        if not enabled:
            return (
                "выключен",
                "ИИ полностью выключен в настройках. Ассистент всё равно может выполнять обычные команды без ИИ."
            )

        if not apply_to_all:
            return (
                "выключен",
                "Интеллектуальная обработка всех команд выключена. После распознавания речи команды обрабатываются обычными правилами."
            )

        if not provider:
            return (
                "не поддерживается",
                "Провайдер ИИ не выбран. Ассистент будет работать без интеллектуальной обработки команд."
            )

        if provider == "stub":
            return (
                "не доступен",
                "В настройках ИИ не выбрана настоящая модель для интеллектуальной обработки команд."
            )

        if provider == "ollama":
            if not ollama_host or not ollama_model:
                return (
                    "не доступен",
                    "В настройках ИИ не выбрана модель Ollama или не указан адрес локального сервера."
                )

            return (
                "включён",
                "ИИ включён для обработки команд. Используется Ollama. Доступность модели можно проверить во вкладке «ИИ»."
            )

        if provider not in SUPPORTED_RUNTIME_AI_PROVIDERS:
            if not provider_endpoint or not remote_model:
                return (
                    "не доступен",
                    "В настройках ИИ не выбрана модель или адрес API для удалённого провайдера."
                )

            return (
                "не поддерживается",
                "Провайдер выбран, но выполнение команд через него ещё не подключено в AI gateway."
            )

        return (
            "не доступен",
            "ИИ сейчас недоступен по неизвестной причине."
        )

    def _get_activation_state(self) -> tuple[str, str]:
        cfg = settings_service.get_all()
        assistant = cfg.get("assistant", {})
        background = cfg.get("background", {})

        activation_mode = assistant.get("activation_mode", "hotkey")
        wake_phrase = assistant.get("voice_activation_phrase", "ассистент")
        hotkey = background.get("hotkey", self.bg_service.hotkey)

        if activation_mode == "voice":
            return (
                "по голосу",
                f"Ассистент реагирует на голосовое обращение «{wake_phrase}». Настраивается во вкладке «Ассистент». Горячая клавиша остаётся запасным способом запуска."
            )

        return (
            "по нажатию",
            f"Ассистент начинает слушать команду после нажатия горячей клавиши: {hotkey}. Настраивается во вкладке «Ассистент»."
        )

    def _compute_overall_status(self, index_running: bool, index_available: bool, mic_ok: bool) -> tuple[str, str, str]:
        if index_running:
            return (
                "Настраивается",
                "process",
                "Ассистент запускается нормально, но сейчас выполняется индексация файлов."
            )

        if not index_available:
            return (
                "Настраивается",
                "process",
                "Индекс файлов отсутствует или повреждён. Ассистент пытается восстановить его в фоне."
            )

        if self.bg_service.is_paused:
            return (
                "На паузе",
                "bad",
                "Ассистент поставлен на паузу. Команды временно не выполняются."
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
        index_status = index.get("status", "")
        index_message = index.get("message", "")
        index_last_error = index.get("last_error", "")

        if index_running:
            index_count = int(index.get("indexed_count", 0))
        else:
            index_count = self._get_persistent_index_count()

        persistent_status = get_index_metadata("index_status", "")
        index_available = index_count > 0 and persistent_status in ("", "ready")

        if not index_available and not index_running:
            self._maybe_recover_missing_index(index_count, index_running, index_status)

        mic_value, mic_tooltip, mic_ok = self._get_mic_state()
        ai_value, ai_tooltip = self._get_ai_state()
        activation_value, activation_tooltip = self._get_activation_state()

        overall_text, overall_kind, overall_tip = self._compute_overall_status(
            index_running=index_running,
            index_available=index_available,
            mic_ok=mic_ok,
        )
        self.overall_status.setText(overall_text)
        self.overall_status.setToolTip(overall_tip)
        apply_status_style(self.overall_status, overall_kind)

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

        self.ai_row.set_value(ai_value)
        self.ai_row.set_tooltip(ai_tooltip)

        self.activation_row.set_value(activation_value)
        self.activation_row.set_tooltip(activation_tooltip)

        if index_running:
            index_value = "выполняется"
            index_tip = (
                f"Сейчас выполняется индексация файлов. "
                f"Уже обработано объектов: {index_count}. {index_message}"
            )
        elif persistent_status == "failed":
            index_value = "ошибка"
            index_tip = (
                f"Последняя индексация завершилась ошибкой: {index_last_error or index_message}. "
                f"Объектов в индексе сейчас: {index_count}."
            )
        elif index_count <= 0:
            index_value = "отсутствует"
            index_tip = (
                "Индекс файлов отсутствует или база была удалена. "
                "Ассистент запустит восстановление индекса в фоне."
            )
        else:
            index_value = "выполнено"
            index_tip = (
                f"Индекс готов. Объектов в индексе: {index_count}. "
                "Индекс нужен для быстрого поиска файлов, папок и приложений."
            )

        self.index_row.set_value(index_value)
        self.index_row.set_tooltip(index_tip)

    def test_voice(self):
        self.notifier.say("Проверка голоса. Ассистент работает.")

    def hide_assistant(self):
        window = self.window()
        if window is not None:
            window.hide()

    def quit_assistant(self):
        try:
            self.bg_service.stop()
        except Exception:
            pass

        app = QApplication.instance()
        if app is not None:
            app.quit()