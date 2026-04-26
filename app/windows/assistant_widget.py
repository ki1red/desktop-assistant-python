from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGridLayout,
    QFrame,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QHBoxLayout,
)

from app.settings_service import settings_service
from app.windows.floating_save_bar import FloatingSaveBar
from app.windows.ui_kit import make_page_title, InfoCard


KEY_OPTIONS = [
    ("Пробел", "space"),
    ("Enter", "enter"),
    ("Tab", "tab"),
    ("F1", "f1"),
    ("F2", "f2"),
    ("F3", "f3"),
    ("F4", "f4"),
    ("F5", "f5"),
    ("F6", "f6"),
    ("F7", "f7"),
    ("F8", "f8"),
    ("F9", "f9"),
    ("F10", "f10"),
    ("F11", "f11"),
    ("F12", "f12"),
    ("A", "a"),
    ("B", "b"),
    ("C", "c"),
    ("D", "d"),
    ("E", "e"),
    ("Q", "q"),
    ("R", "r"),
    ("S", "s"),
    ("W", "w"),
]


def _display_hotkey(ctrl: bool, alt: bool, shift: bool, win: bool, key_label: str) -> str:
    parts = []
    if ctrl:
        parts.append("Ctrl")
    if alt:
        parts.append("Alt")
    if shift:
        parts.append("Shift")
    if win:
        parts.append("Win")
    parts.append(key_label)
    return " + ".join(parts)


def _build_hotkey_string(ctrl: bool, alt: bool, shift: bool, win: bool, key_value: str) -> str:
    parts = []
    if ctrl:
        parts.append("<ctrl>")
    if alt:
        parts.append("<alt>")
    if shift:
        parts.append("<shift>")
    if win:
        parts.append("<cmd>")
    parts.append(f"<{key_value}>")
    return "+".join(parts)


def _parse_hotkey(raw: str) -> dict:
    raw = raw or "<ctrl>+<alt>+<space>"
    cleaned = raw.replace("<", "").replace(">", "").lower()
    parts = [p.strip() for p in cleaned.split("+") if p.strip()]

    modifiers = set(parts)
    keys = [p for p in parts if p not in {"ctrl", "alt", "shift", "cmd", "win"}]

    key_value = keys[-1] if keys else "space"

    return {
        "ctrl": "ctrl" in modifiers,
        "alt": "alt" in modifiers,
        "shift": "shift" in modifiers,
        "win": "cmd" in modifiers or "win" in modifiers,
        "key": key_value,
    }


class AssistantWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._loading = False
        self._dirty = False
        self._saved_form_state = {}
        self._voices_loaded = False

        self._build_ui()
        self._connect_signals()
        self._load_from_settings(reset_dirty=True)

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
            "Здесь настраиваются голос ассистента, способ активации и речевое сопровождение действий."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 18px; color: #303846;")
        card.layout.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        self.voice_combo = QComboBox()
        self.voice_combo.setToolTip(
            "Выберите голос, которым ассистент будет озвучивать ответы и комментарии."
        )

        self.activation_combo = QComboBox()
        self.activation_combo.addItem("По нажатию", "hotkey")
        self.activation_combo.addItem("По голосу", "voice")
        self.activation_combo.setToolTip(
            "Способ активации ассистента. Сейчас полностью работает активация по нажатию. "
            "Голосовая активация сохраняется в настройках, но сам wake-listener ещё нужно реализовать."
        )

        self.hotkey_label = QLabel("Горячая клавиша:")
        self.hotkey_panel = QFrame()
        hotkey_layout = QVBoxLayout(self.hotkey_panel)
        hotkey_layout.setContentsMargins(0, 0, 0, 0)
        hotkey_layout.setSpacing(8)

        hotkey_checks = QHBoxLayout()

        self.ctrl_checkbox = QCheckBox("Ctrl")
        self.alt_checkbox = QCheckBox("Alt")
        self.shift_checkbox = QCheckBox("Shift")
        self.win_checkbox = QCheckBox("Win")

        self.key_combo = QComboBox()
        for label, value in KEY_OPTIONS:
            self.key_combo.addItem(label, value)

        for cb in [
            self.ctrl_checkbox,
            self.alt_checkbox,
            self.shift_checkbox,
            self.win_checkbox,
        ]:
            cb.setToolTip("Выберите клавиши-модификаторы для горячей клавиши ассистента.")
            hotkey_checks.addWidget(cb)

        self.key_combo.setToolTip("Основная клавиша сочетания.")
        hotkey_checks.addWidget(self.key_combo)
        hotkey_checks.addStretch(1)

        self.hotkey_preview = QLabel()
        self.hotkey_preview.setStyleSheet("font-size: 15px; color: #687386;")
        self.hotkey_preview.setToolTip("Так выбранная горячая клавиша будет выглядеть для пользователя.")

        hotkey_layout.addLayout(hotkey_checks)
        hotkey_layout.addWidget(self.hotkey_preview)

        self.wake_phrase_label = QLabel("Обращение:")
        self.voice_panel = QFrame()
        voice_layout = QVBoxLayout(self.voice_panel)
        voice_layout.setContentsMargins(0, 0, 0, 0)

        self.wake_phrase_edit = QLineEdit()
        self.wake_phrase_edit.setPlaceholderText("Например: ассистент")
        self.wake_phrase_edit.setToolTip(
            "Фраза, на которую ассистент будет реагировать в будущем режиме голосовой активации."
        )

        voice_layout.addWidget(self.wake_phrase_edit)

        self.comment_actions_checkbox = QCheckBox("Комментировать свои действия")
        self.comment_actions_checkbox.setToolTip(
            "Если включено, ассистент будет говорить «обрабатываю», «выполнено» и другие фразы. "
            "Если выключено, команды будут выполняться молча. Звуковой сигнал начала прослушивания останется."
        )

        form.addRow("Голос:", self.voice_combo)
        form.addRow("Активация:", self.activation_combo)
        form.addRow(self.hotkey_label, self.hotkey_panel)
        form.addRow(self.wake_phrase_label, self.voice_panel)
        form.addRow("", self.comment_actions_checkbox)

        card.layout.addLayout(form)
        root.addWidget(card)
        root.addStretch(1)

        self.save_bar = FloatingSaveBar(self, "Сохранить")
        self.save_bar.clicked.connect(self.save_settings)

    def _connect_signals(self):
        self.voice_combo.currentIndexChanged.connect(self._update_dirty)
        self.activation_combo.currentIndexChanged.connect(self._on_activation_changed)
        self.ctrl_checkbox.stateChanged.connect(self._on_hotkey_changed)
        self.alt_checkbox.stateChanged.connect(self._on_hotkey_changed)
        self.shift_checkbox.stateChanged.connect(self._on_hotkey_changed)
        self.win_checkbox.stateChanged.connect(self._on_hotkey_changed)
        self.key_combo.currentIndexChanged.connect(self._on_hotkey_changed)
        self.wake_phrase_edit.textChanged.connect(self._update_dirty)
        self.comment_actions_checkbox.stateChanged.connect(self._update_dirty)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_bar"):
            self.save_bar.reposition()

    def on_tab_activated(self):
        if not self._voices_loaded:
            self._load_voices()

        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def on_tab_deactivated(self):
        if self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot
        if not self._dirty:
            self._load_from_settings(reset_dirty=True)

    def _load_voices(self):
        current_voice_id = self.voice_combo.currentData() or ""
        current_voice_text = self.voice_combo.currentText()

        self.voice_combo.clear()
        self.voice_combo.addItem("Системный голос по умолчанию", "")

        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []

            for voice in voices:
                voice_id = getattr(voice, "id", "") or ""
                voice_name = getattr(voice, "name", "") or voice_id or "Без названия"
                self.voice_combo.addItem(voice_name, voice_id)

            try:
                engine.stop()
            except Exception:
                pass

        except Exception:
            if current_voice_id:
                self.voice_combo.addItem(current_voice_text or current_voice_id, current_voice_id)

        if current_voice_id:
            idx = self.voice_combo.findData(current_voice_id)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

        self._voices_loaded = True

    def _set_combo_by_data(self, combo: QComboBox, data, fallback_index: int = 0):
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

        combo.setCurrentIndex(fallback_index)

    def _load_from_settings(self, reset_dirty: bool):
        self._loading = True

        self.config = settings_service.get_all()
        assistant = self.config.get("assistant", {})
        background = self.config.get("background", {})
        voice = self.config.get("voice", {})

        saved_voice_id = voice.get("voice_id", "")
        saved_voice_name = voice.get("voice_name", "")

        if self.voice_combo.count() == 0:
            self.voice_combo.addItem("Системный голос по умолчанию", "")

        if saved_voice_id and self.voice_combo.findData(saved_voice_id) < 0:
            self.voice_combo.addItem(saved_voice_name or saved_voice_id, saved_voice_id)

        self._set_combo_by_data(self.voice_combo, saved_voice_id)

        activation_mode = assistant.get("activation_mode", "hotkey")
        self._set_combo_by_data(self.activation_combo, activation_mode)

        parsed = _parse_hotkey(background.get("hotkey", "<ctrl>+<alt>+<space>"))
        self.ctrl_checkbox.setChecked(parsed["ctrl"])
        self.alt_checkbox.setChecked(parsed["alt"])
        self.shift_checkbox.setChecked(parsed["shift"])
        self.win_checkbox.setChecked(parsed["win"])
        self._set_combo_by_data(self.key_combo, parsed["key"])

        self.wake_phrase_edit.setText(assistant.get("voice_activation_phrase", "ассистент"))
        self.comment_actions_checkbox.setChecked(bool(assistant.get("comment_actions", True)))

        self._loading = False
        self._update_activation_panel()
        self._update_hotkey_preview()

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self.save_bar.set_dirty(self._dirty)

    def _capture_form_state(self) -> dict:
        key_label = self.key_combo.currentText()
        key_value = self.key_combo.currentData() or "space"

        return {
            "voice_id": self.voice_combo.currentData() or "",
            "voice_name": self.voice_combo.currentText() if self.voice_combo.currentData() else "",
            "activation_mode": self.activation_combo.currentData() or "hotkey",
            "hotkey": _build_hotkey_string(
                self.ctrl_checkbox.isChecked(),
                self.alt_checkbox.isChecked(),
                self.shift_checkbox.isChecked(),
                self.win_checkbox.isChecked(),
                key_value,
            ),
            "hotkey_preview": _display_hotkey(
                self.ctrl_checkbox.isChecked(),
                self.alt_checkbox.isChecked(),
                self.shift_checkbox.isChecked(),
                self.win_checkbox.isChecked(),
                key_label,
            ),
            "voice_activation_phrase": self.wake_phrase_edit.text().strip(),
            "comment_actions": self.comment_actions_checkbox.isChecked(),
        }

    def _update_dirty(self):
        if self._loading:
            return

        self._dirty = self._capture_form_state() != self._saved_form_state
        self.save_bar.set_dirty(self._dirty)

    def _on_activation_changed(self):
        self._update_activation_panel()
        self._update_dirty()

    def _on_hotkey_changed(self):
        self._update_hotkey_preview()
        self._update_dirty()

    def _update_activation_panel(self):
        mode = self.activation_combo.currentData() or "hotkey"

        hotkey_visible = mode == "hotkey"
        voice_visible = mode == "voice"

        self.hotkey_label.setVisible(hotkey_visible)
        self.hotkey_panel.setVisible(hotkey_visible)

        self.wake_phrase_label.setVisible(voice_visible)
        self.voice_panel.setVisible(voice_visible)

    def _update_hotkey_preview(self):
        state = self._capture_form_state()
        self.hotkey_preview.setText(f"Текущее сочетание: {state['hotkey_preview']}")

    def save_settings(self):
        state = self._capture_form_state()

        def mutator(cfg: dict):
            cfg.setdefault("assistant", {})
            cfg.setdefault("background", {})
            cfg.setdefault("voice", {})

            cfg["assistant"]["activation_mode"] = state["activation_mode"]
            cfg["assistant"]["voice_activation_phrase"] = state["voice_activation_phrase"]
            cfg["assistant"]["comment_actions"] = state["comment_actions"]

            cfg["background"]["hotkey"] = state["hotkey"]

            cfg["voice"]["voice_id"] = state["voice_id"]
            cfg["voice"]["voice_name"] = state["voice_name"]
            cfg["voice"]["enabled"] = state["comment_actions"]

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False

        self.save_bar.show_saved("Успешно сохранено")