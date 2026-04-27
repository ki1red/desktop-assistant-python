import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLabel,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QFormLayout,
)

from app.settings_service import settings_service
from app.logger import get_logger
from app.windows.ui_kit import make_page_title
from app.windows.floating_save_bar import FloatingSaveBar


logger = get_logger("assistant_widget")


HOTKEY_KEY_OPTIONS = [
    ("Пробел", "<space>"),
    ("Enter", "<enter>"),
    ("F8", "<f8>"),
    ("F9", "<f9>"),
    ("F10", "<f10>"),
    ("F11", "<f11>"),
    ("F12", "<f12>"),
]


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
        self.layout.setSpacing(16)


class AssistantWidget(QWidget):
    def __init__(self):
        super().__init__()

        logger.info("AssistantWidget | init_start")

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._loading_controls = False
        self._dirty = False
        self._saved_form_state = {}

        self._build_ui()
        self._connect_change_signals()
        self._load_from_settings(reset_dirty=True)

        logger.info("AssistantWidget | init_done")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = make_page_title("Ассистент")
        header.addWidget(title, 0, 1)

        root.addLayout(header)

        card = InfoCard()

        description = QLabel(
            "Здесь настраивается поведение ассистента: голос, способ активации "
            "и озвучивание действий."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 18px; color: #4b5563;")
        card.layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        self.voice_combo = QComboBox()
        self.voice_combo.setToolTip(
            "Голос, которым ассистент будет озвучивать ответы и служебные сообщения."
        )

        self.activation_combo = QComboBox()
        self.activation_combo.addItem("По нажатию", "hotkey")
        self.activation_combo.addItem("По голосу", "voice")
        self.activation_combo.setToolTip(
            "Способ активации определяет, как ассистент начинает слушать команду."
        )

        self.hotkey_widget = QWidget()
        hotkey_layout = QHBoxLayout(self.hotkey_widget)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        hotkey_layout.setSpacing(10)

        self.ctrl_checkbox = QCheckBox("Ctrl")
        self.alt_checkbox = QCheckBox("Alt")
        self.shift_checkbox = QCheckBox("Shift")

        self.hotkey_key_combo = QComboBox()
        for label, value in HOTKEY_KEY_OPTIONS:
            self.hotkey_key_combo.addItem(label, value)

        hotkey_layout.addWidget(self.ctrl_checkbox)
        hotkey_layout.addWidget(self.alt_checkbox)
        hotkey_layout.addWidget(self.shift_checkbox)
        hotkey_layout.addWidget(QLabel("+"))
        hotkey_layout.addWidget(self.hotkey_key_combo, 1)

        self.hotkey_widget.setToolTip(
            "Сочетание клавиш, по которому ассистент начинает слушать команду. "
            "Например: Ctrl + Alt + Пробел."
        )

        self.voice_phrase_edit = QLineEdit()
        self.voice_phrase_edit.setPlaceholderText("Например: ассистент")
        self.voice_phrase_edit.setToolTip(
            "Фраза, после которой ассистент активируется голосом и начинает слушать команду."
        )

        self.comment_actions_checkbox = QCheckBox("Комментировать свои действия")
        self.comment_actions_checkbox.setToolTip(
            "Если включено, ассистент будет голосом говорить: «Слушаю», "
            "«Обрабатываю запрос», «Готово» и похожие сообщения. "
            "Звук начала прослушивания остаётся отдельно."
        )

        form.addRow("Голос ассистента:", self.voice_combo)
        form.addRow("Способ активации:", self.activation_combo)
        form.addRow("Горячая клавиша:", self.hotkey_widget)
        form.addRow("Обращение:", self.voice_phrase_edit)
        form.addRow("", self.comment_actions_checkbox)

        card.layout.addLayout(form)
        root.addWidget(card)
        root.addStretch(1)

        self.save_bar = FloatingSaveBar(self, "Сохранить")
        self.save_bar.clicked.connect(self.save_settings)

    def _connect_change_signals(self):
        self.voice_combo.currentIndexChanged.connect(self._update_save_buttons)
        self.activation_combo.currentIndexChanged.connect(self._on_activation_changed)

        self.ctrl_checkbox.stateChanged.connect(self._update_save_buttons)
        self.alt_checkbox.stateChanged.connect(self._update_save_buttons)
        self.shift_checkbox.stateChanged.connect(self._update_save_buttons)
        self.hotkey_key_combo.currentIndexChanged.connect(self._update_save_buttons)

        self.voice_phrase_edit.textChanged.connect(self._update_save_buttons)
        self.comment_actions_checkbox.stateChanged.connect(self._update_save_buttons)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_bar"):
            self.save_bar.reposition()

    def on_tab_activated(self):
        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def on_tab_deactivated(self):
        if self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot

        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _on_activation_changed(self):
        self._update_activation_visibility()
        self._update_save_buttons()

    def _update_activation_visibility(self):
        activation_mode = self.activation_combo.currentData() or "hotkey"

        self.hotkey_widget.setVisible(activation_mode == "hotkey")
        self.voice_phrase_edit.setVisible(activation_mode == "voice")

        if hasattr(self, "save_bar"):
            self.save_bar.reposition()

    def _load_voices(self, selected_voice_id: str):
        self.voice_combo.clear()
        self.voice_combo.addItem("Системный голос", "")

        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []

            for voice in voices:
                voice_id = getattr(voice, "id", "") or ""
                voice_name = getattr(voice, "name", "") or voice_id

                if voice_id:
                    self.voice_combo.addItem(voice_name, voice_id)

            try:
                engine.stop()
            except Exception:
                pass

        except Exception as e:
            logger.warning("AssistantWidget | не удалось получить список голосов: %s", e)

        if selected_voice_id:
            index = self.voice_combo.findData(selected_voice_id)
            if index >= 0:
                self.voice_combo.setCurrentIndex(index)
            else:
                self.voice_combo.addItem(f"Сохранённый голос: {selected_voice_id}", selected_voice_id)
                self.voice_combo.setCurrentIndex(self.voice_combo.count() - 1)
        else:
            self.voice_combo.setCurrentIndex(0)

    def _set_activation_mode(self, value: str):
        for i in range(self.activation_combo.count()):
            if self.activation_combo.itemData(i) == value:
                self.activation_combo.setCurrentIndex(i)
                return

        self.activation_combo.setCurrentIndex(0)

    def _compose_hotkey(self) -> str:
        parts = []

        if self.ctrl_checkbox.isChecked():
            parts.append("<ctrl>")

        if self.alt_checkbox.isChecked():
            parts.append("<alt>")

        if self.shift_checkbox.isChecked():
            parts.append("<shift>")

        key = self.hotkey_key_combo.currentData() or "<space>"
        parts.append(key)

        return "+".join(parts)

    def _load_hotkey_to_controls(self, hotkey: str):
        hotkey = (hotkey or "<ctrl>+<alt>+<space>").lower()

        self.ctrl_checkbox.setChecked("<ctrl>" in hotkey or "ctrl" in hotkey)
        self.alt_checkbox.setChecked("<alt>" in hotkey or "alt" in hotkey)
        self.shift_checkbox.setChecked("<shift>" in hotkey or "shift" in hotkey)

        selected_key = "<space>"

        for _, value in HOTKEY_KEY_OPTIONS:
            if value.lower() in hotkey:
                selected_key = value
                break

        for i in range(self.hotkey_key_combo.count()):
            if self.hotkey_key_combo.itemData(i) == selected_key:
                self.hotkey_key_combo.setCurrentIndex(i)
                return

        self.hotkey_key_combo.setCurrentIndex(0)

    def _load_from_settings(self, reset_dirty: bool):
        self._loading_controls = True

        self.config = settings_service.get_all()

        assistant = self.config.get("assistant", {})
        background = self.config.get("background", {})
        voice = self.config.get("voice", {})

        selected_voice_id = voice.get("voice_id", "")
        self._load_voices(selected_voice_id)

        activation_mode = assistant.get("activation_mode", "hotkey")
        self._set_activation_mode(activation_mode)

        self._load_hotkey_to_controls(background.get("hotkey", "<ctrl>+<alt>+<space>"))

        self.voice_phrase_edit.setText(
            assistant.get("voice_activation_phrase", "ассистент")
        )

        self.comment_actions_checkbox.setChecked(
            bool(voice.get("enabled", True))
        )

        self._loading_controls = False

        self._update_activation_visibility()

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self._set_save_buttons_enabled(self._dirty)

    def _capture_form_state(self) -> dict:
        return {
            "voice_id": self.voice_combo.currentData() or "",
            "activation_mode": self.activation_combo.currentData() or "hotkey",
            "hotkey": self._compose_hotkey(),
            "voice_activation_phrase": self.voice_phrase_edit.text().strip() or "ассистент",
            "comment_actions": self.comment_actions_checkbox.isChecked(),
        }

    def _set_save_buttons_enabled(self, enabled: bool):
        self.save_bar.set_dirty(enabled)

    def _update_save_buttons(self):
        if self._loading_controls:
            return

        self._dirty = self._capture_form_state() != self._saved_form_state
        self._set_save_buttons_enabled(self._dirty)

    def save_settings(self):
        state = self._capture_form_state()

        def mutator(cfg: dict):
            cfg.setdefault("voice", {})
            cfg.setdefault("assistant", {})
            cfg.setdefault("background", {})

            cfg["voice"]["voice_id"] = state["voice_id"]
            cfg["voice"]["enabled"] = state["comment_actions"]

            cfg["assistant"]["activation_mode"] = state["activation_mode"]
            cfg["assistant"]["voice_activation_phrase"] = state["voice_activation_phrase"]

            cfg["background"]["hotkey"] = state["hotkey"]

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False
        self._set_save_buttons_enabled(False)

        self.save_bar.show_saved("Сохранено!")