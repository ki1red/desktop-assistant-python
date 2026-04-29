import threading

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QProgressBar,
    QGridLayout,
    QFrame,
    QToolButton,
)

from app.settings_service import settings_service
from app.speech.recorder import (
    list_input_devices,
    list_output_devices,
    resolve_input_device,
    refresh_audio_devices,
)
from app.windows.floating_save_bar import FloatingSaveBar


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


def _normalize_device_name(device_name: str) -> str:
    return " ".join((device_name or "").lower().replace("ё", "е").split())


def _device_name_matches(selected_name: str, real_name: str) -> bool:
    selected = _normalize_device_name(selected_name)
    real = _normalize_device_name(real_name)

    if not selected or not real:
        return False

    return selected == real or selected in real or real in selected


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


class AudioSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

        self._loading_controls = False
        self._refreshing_device_lists = False
        self._dirty = False
        self._saved_form_state = {}

        self._meter_stream = None
        self._meter_lock = threading.Lock()
        self._latest_level = 0
        self._calibration_samples = []
        self._calibration_active = False
        self._selected_mic_value = self.config.get("audio", {}).get("input_device_name", "") or ""
        self._selected_output_value = self.config.get("audio", {}).get("output_device_name", "") or ""

        self._build_ui()
        self._connect_change_signals()
        self._load_from_settings(reset_dirty=True)

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot

        if not self._dirty:
            self._load_from_settings(reset_dirty=True)
        else:
            self.refresh_status()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 34, 48, 34)
        root.setSpacing(24)

        header = QGridLayout()
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 2)
        header.setColumnStretch(2, 1)

        title = _make_page_title("Аудио")
        self.overall_status = _make_status_badge()

        header.addWidget(title, 0, 1)
        header.addWidget(self.overall_status, 0, 2, alignment=Qt.AlignRight | Qt.AlignVCenter)

        root.addLayout(header)

        card = InfoCard()

        top_row = QHBoxLayout()

        self.mic_title_label = QLabel("Микрофон:")
        self.mic_title_label.setStyleSheet("font-size: 26px; font-weight: 500;")

        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumWidth(430)

        self.test_mic_btn = QPushButton("Проверить микрофон")
        self.test_mic_btn.clicked.connect(self.toggle_meter)

        self.auto_calibrate_btn = QPushButton("Автонастройка")
        self.auto_calibrate_btn.clicked.connect(self.auto_calibrate)

        top_row.addWidget(self.mic_title_label)
        top_row.addWidget(self.mic_combo, 1)
        top_row.addWidget(self.test_mic_btn)
        top_row.addWidget(self.auto_calibrate_btn)

        card.layout.addLayout(top_row)

        self.microphone_enabled_checkbox = QCheckBox("Разрешить использование микрофона")
        self.microphone_enabled_checkbox.setToolTip(
            "Если выключить этот пункт, ассистент не будет использовать микрофон для голосовых команд."
        )

        card.layout.addWidget(self.microphone_enabled_checkbox)

        self.meter_panel = QFrame()
        self.meter_panel.setObjectName("MeterPanel")
        self.meter_panel.setVisible(False)
        self.meter_panel.setStyleSheet("""
            QFrame#MeterPanel {
                background: #f7f8fb;
                border: 1px solid #dde2ea;
                border-radius: 12px;
            }
        """)

        meter_layout = QVBoxLayout(self.meter_panel)
        meter_layout.setContentsMargins(18, 14, 18, 14)

        self.meter_state_label = QLabel("Тест микрофона: выключен")
        self.meter_state_label.setStyleSheet("font-size: 16px; font-weight: 500;")

        self.meter_bar = QProgressBar()
        self.meter_bar.setRange(0, 100)
        self.meter_bar.setValue(0)
        self.meter_bar.setTextVisible(True)

        self.meter_hint_label = QLabel("Уровень сигнала пока не оценён.")
        self.meter_hint_label.setWordWrap(True)
        self.meter_hint_label.setStyleSheet("font-size: 15px; color: #555;")

        meter_layout.addWidget(self.meter_state_label)
        meter_layout.addWidget(self.meter_bar)
        meter_layout.addWidget(self.meter_hint_label)

        card.layout.addWidget(self.meter_panel)

        root.addWidget(card)

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Расширенные настройки")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.setArrowType(Qt.RightArrow)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.advanced_toggle.setStyleSheet("""
            QToolButton {
                font-size: 24px;
                font-weight: 500;
                border: none;
                padding: 10px 0;
            }
        """)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)

        root.addWidget(self.advanced_toggle)

        self.advanced_panel = QFrame()
        self.advanced_panel.setObjectName("AdvancedPanel")
        self.advanced_panel.setVisible(False)
        self.advanced_panel.setStyleSheet("""
            QFrame#AdvancedPanel {
                background: #ffffff;
                border: 1px solid #dde2ea;
                border-radius: 14px;
            }
        """)

        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(24, 20, 24, 20)
        advanced_layout.setSpacing(14)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        self.output_combo = QComboBox()

        self.enabled_voice_checkbox = QCheckBox("Включить голосовые ответы")

        self.input_gain_edit = QLineEdit()
        self.max_record_edit = QLineEdit()
        self.min_record_edit = QLineEdit()
        self.silence_stop_edit = QLineEdit()
        self.silence_threshold_edit = QLineEdit()

        self.rate_edit = QLineEdit()
        self.volume_edit = QLineEdit()
        self.heartbeat_edit = QLineEdit()

        self.refresh_devices_btn = QPushButton("Обновить список устройств")
        self.refresh_devices_btn.clicked.connect(lambda: self.refresh_devices(force_refresh=True))

        form.addRow("Устройство вывода:", self.output_combo)
        form.addRow("", self.enabled_voice_checkbox)
        form.addRow("Программное усиление микрофона:", self.input_gain_edit)
        form.addRow("Максимальная длина записи, сек:", self.max_record_edit)
        form.addRow("Минимальная длина записи, сек:", self.min_record_edit)
        form.addRow("Пауза для остановки, сек:", self.silence_stop_edit)
        form.addRow("Порог тишины:", self.silence_threshold_edit)
        form.addRow("Скорость речи:", self.rate_edit)
        form.addRow("Громкость:", self.volume_edit)
        form.addRow("Интервал фразы «ещё работаю», сек:", self.heartbeat_edit)
        form.addRow("", self.refresh_devices_btn)

        advanced_layout.addLayout(form)

        root.addWidget(self.advanced_panel)
        root.addStretch(1)

        self.save_bar = FloatingSaveBar(self, "Сохранить")
        self.save_bar.clicked.connect(self.save_settings)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_meter_ui)
        self.timer.start(100)

        self.devices_timer = QTimer(self)
        self.devices_timer.timeout.connect(self._auto_refresh_devices_if_visible)
        self.devices_timer.start(5000)

    def _connect_change_signals(self):
        self.mic_combo.currentIndexChanged.connect(self._on_mic_selection_changed)
        self.output_combo.currentIndexChanged.connect(self._on_output_selection_changed)
        self.mic_combo.currentIndexChanged.connect(self._update_save_buttons)
        self.output_combo.currentIndexChanged.connect(self._update_save_buttons)
        self.microphone_enabled_checkbox.stateChanged.connect(self._update_save_buttons)
        self.enabled_voice_checkbox.stateChanged.connect(self._update_save_buttons)

        for edit in [
            self.input_gain_edit,
            self.max_record_edit,
            self.min_record_edit,
            self.silence_stop_edit,
            self.silence_threshold_edit,
            self.rate_edit,
            self.volume_edit,
            self.heartbeat_edit,
        ]:
            edit.textChanged.connect(self._update_save_buttons)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_bar"):
            self.save_bar.reposition()

    def _toggle_advanced(self, checked: bool):
        self.advanced_panel.setVisible(checked)
        self.advanced_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.save_bar.reposition()

    def on_tab_activated(self):
        if not self._dirty:
            self.refresh_devices(force_refresh=True)
            self.refresh_status()

    def on_tab_deactivated(self):
        if self._dirty:
            self._load_from_settings(reset_dirty=True)

    def showEvent(self, event):
        super().showEvent(event)

        if not self._dirty:
            self.refresh_devices(force_refresh=True)
            self.refresh_status()

    def _auto_refresh_devices_if_visible(self):
        if self._meter_stream is not None:
            return

        if self.isVisible() and not self._dirty:
            self.refresh_devices(force_refresh=True)

    def _on_mic_selection_changed(self):
        if self._loading_controls or self._refreshing_device_lists:
            return

        self._selected_mic_value = self.mic_combo.currentData() or ""

    def _on_output_selection_changed(self):
        if self._loading_controls or self._refreshing_device_lists:
            return

        self._selected_output_value = self.output_combo.currentData() or ""

    def _populate_device_lists(self, selected_mic: str, selected_output: str, force_refresh: bool = False):
        self._refreshing_device_lists = True
        self.mic_combo.blockSignals(True)
        self.output_combo.blockSignals(True)

        if force_refresh:
            refresh_audio_devices(force=True)

        self.mic_combo.clear()
        self.mic_combo.addItem("Не выбрано", "")

        input_devices = []
        output_devices = []

        try:
            input_devices = list_input_devices(refresh=False)
            for dev in input_devices:
                self.mic_combo.addItem(dev["name"], dev["name"])
        except Exception as e:
            self.mic_combo.addItem(f"Ошибка получения устройств: {e}", "")

        selected_mic = selected_mic or ""
        if selected_mic:
            idx = self.mic_combo.findData(selected_mic)

            if idx < 0:
                for i in range(self.mic_combo.count()):
                    if _device_name_matches(selected_mic, self.mic_combo.itemData(i) or ""):
                        idx = i
                        break

            if idx < 0:
                self.mic_combo.addItem(f"Недоступно: {selected_mic}", selected_mic)
                last_index = self.mic_combo.count() - 1
                self.mic_combo.insertItem(1, self.mic_combo.itemText(last_index), self.mic_combo.itemData(last_index))
                self.mic_combo.removeItem(self.mic_combo.count() - 1)
                idx = 1

            self.mic_combo.setCurrentIndex(idx)
        else:
            self.mic_combo.setCurrentIndex(0)

        self.output_combo.clear()
        self.output_combo.addItem("Не выбрано", "")

        try:
            output_devices = list_output_devices(refresh=False)
            for dev in output_devices:
                self.output_combo.addItem(dev["name"], dev["name"])
        except Exception as e:
            self.output_combo.addItem(f"Ошибка получения устройств: {e}", "")

        selected_output = selected_output or ""
        if selected_output:
            idx = self.output_combo.findData(selected_output)

            if idx < 0:
                for i in range(self.output_combo.count()):
                    if _device_name_matches(selected_output, self.output_combo.itemData(i) or ""):
                        idx = i
                        break

            if idx < 0:
                self.output_combo.addItem(f"Недоступно: {selected_output}", selected_output)
                idx = self.output_combo.count() - 1

            self.output_combo.setCurrentIndex(idx)
        else:
            self.output_combo.setCurrentIndex(0)

        self.mic_combo.blockSignals(False)
        self.output_combo.blockSignals(False)
        self._refreshing_device_lists = False

    def refresh_devices(self, force_refresh: bool = True):
        if self._meter_stream is not None:
            self.refresh_status()
            return

        if self._dirty:
            selected_mic = self._selected_mic_value
            selected_output = self._selected_output_value
        else:
            cfg = settings_service.get_all()
            selected_mic = cfg.get("audio", {}).get("input_device_name", "") or ""
            selected_output = cfg.get("audio", {}).get("output_device_name", "") or ""
            self._selected_mic_value = selected_mic
            self._selected_output_value = selected_output

        self._populate_device_lists(selected_mic, selected_output, force_refresh=force_refresh)
        self.refresh_status()

    def _load_from_settings(self, reset_dirty: bool):
        self._loading_controls = True

        self.config = settings_service.get_all()
        audio = self.config.get("audio", {})
        voice = self.config.get("voice", {})
        self._selected_mic_value = audio.get("input_device_name", "") or ""
        self._selected_output_value = audio.get("output_device_name", "") or ""

        self._populate_device_lists(
            self._selected_mic_value,
            self._selected_output_value,
            force_refresh=True,
        )

        self.microphone_enabled_checkbox.setChecked(audio.get("microphone_enabled", True))
        self.enabled_voice_checkbox.setChecked(voice.get("enabled", True))

        self.input_gain_edit.setText(str(audio.get("input_gain", 1.0)))
        self.max_record_edit.setText(str(audio.get("max_record_seconds", 12)))
        self.min_record_edit.setText(str(audio.get("min_record_seconds", 0.8)))
        self.silence_stop_edit.setText(str(audio.get("silence_duration_stop_sec", 1.0)))
        self.silence_threshold_edit.setText(str(audio.get("silence_threshold", 500)))

        self.rate_edit.setText(str(voice.get("rate", 185)))
        self.volume_edit.setText(str(voice.get("volume", 1.0)))
        self.heartbeat_edit.setText(str(voice.get("heartbeat_interval_sec", 8)))

        self._loading_controls = False

        if reset_dirty:
            self._saved_form_state = self._capture_form_state()
            self._dirty = False

        self._set_save_buttons_enabled(self._dirty)
        self.refresh_status()

    def _capture_form_state(self) -> dict:
        return {
            "microphone_enabled": self.microphone_enabled_checkbox.isChecked(),
            "input_device_name": self._selected_mic_value,
            "output_device_name": self._selected_output_value,
            "voice_enabled": self.enabled_voice_checkbox.isChecked(),
            "input_gain": self.input_gain_edit.text().strip(),
            "max_record_seconds": self.max_record_edit.text().strip(),
            "min_record_seconds": self.min_record_edit.text().strip(),
            "silence_duration_stop_sec": self.silence_stop_edit.text().strip(),
            "silence_threshold": self.silence_threshold_edit.text().strip(),
            "rate": self.rate_edit.text().strip(),
            "volume": self.volume_edit.text().strip(),
            "heartbeat_interval_sec": self.heartbeat_edit.text().strip(),
        }

    def _set_save_buttons_enabled(self, enabled: bool):
        self.save_bar.set_dirty(enabled)

    def _update_save_buttons(self):
        if self._loading_controls:
            return

        self._dirty = self._capture_form_state() != self._saved_form_state
        self._set_save_buttons_enabled(self._dirty)
        self.refresh_status()

    def _selected_mic_available(self, selected_mic: str) -> bool:
        if not selected_mic:
            return False

        try:
            for dev in list_input_devices(refresh=False):
                if _device_name_matches(selected_mic, dev["name"]):
                    return True
        except Exception:
            return False

        return False

    def _audio_status(self) -> tuple[str, str, str]:
        if not self.microphone_enabled_checkbox.isChecked():
            return (
                "Недоступно",
                "bad",
                "Использование микрофона выключено. Без микрофона ассистент не сможет принимать голосовые команды."
            )

        selected_mic = self._selected_mic_value
        if not selected_mic:
            return "Недоступно", "bad", "Микрофон не выбран. Выберите устройство ввода из списка."

        if not self._selected_mic_available(selected_mic):
            return (
                "Недоступно",
                "bad",
                "Выбранный микрофон сейчас не найден. "
                "Если вы только что подключили устройство, подождите несколько секунд или нажмите «Обновить список устройств»."
            )

        if self._meter_stream is not None and self.meter_bar.value() <= 2:
            return "Проверяется", "process", "Тест микрофона включён, но пока сигнал почти не слышен."

        return "Доступно", "ok", "Микрофон выбран. Для проверки уровня нажмите «Проверить микрофон»."

    def refresh_status(self):
        status, status_kind, tip = self._audio_status()

        self.overall_status.setText(status)
        self.overall_status.setToolTip(tip)
        self.mic_title_label.setToolTip(tip)
        self.mic_combo.setToolTip(tip)

        _apply_status_style(self.overall_status, status_kind)

    def _find_selected_input_device_index(self):
        selected_name = self._selected_mic_value
        if not selected_name:
            return None

        try:
            device_index, _resolved_name = resolve_input_device(
                selected_name=selected_name,
                allow_fallback=False,
                refresh=True,
            )
            return device_index
        except Exception:
            return None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            return

        audio = indata.astype(np.float32)
        rms = float(np.sqrt(np.mean(np.square(audio))))

        try:
            gain = float(self.input_gain_edit.text().strip() or "1.0")
        except Exception:
            gain = 1.0

        cfg = settings_service.get_all()
        audio_cfg = cfg.get("audio", {})

        auto_gain_enabled = bool(audio_cfg.get("auto_input_gain_enabled", True))
        auto_gain_target_rms = float(audio_cfg.get("auto_gain_target_rms", 2200))
        max_auto_gain = float(audio_cfg.get("max_auto_gain", 10.0))

        effective_gain = gain
        if auto_gain_enabled and rms > 1.0:
            desired_gain = auto_gain_target_rms / rms
            desired_gain = max(1.0, min(max_auto_gain, desired_gain))
            effective_gain = max(gain, desired_gain)

        rms *= effective_gain
        level = int(min(100, (rms / 3000.0) * 100))
        level = max(0, min(level, 100))

        with self._meter_lock:
            self._latest_level = level
            if self._calibration_active:
                self._calibration_samples.append(level)

    def toggle_meter(self):
        if self._meter_stream is None:
            self._start_meter()
        else:
            self._stop_meter()

    def _start_meter(self) -> bool:
        if self._meter_stream is not None:
            return True

        device_index = self._find_selected_input_device_index()
        if device_index is None:
            QMessageBox.warning(self, "Нет микрофона", "Сначала выберите доступный микрофон.")
            self.refresh_devices(force_refresh=True)
            return False

        try:
            self._meter_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                blocksize=1024,
                dtype="int16",
                device=device_index,
                callback=self._audio_callback
            )
            self._meter_stream.start()

            self.meter_panel.setVisible(True)
            self.meter_state_label.setText("Тест микрофона: включён")
            self.test_mic_btn.setText("Остановить тест")

            self.refresh_status()
            return True

        except Exception as e:
            self._meter_stream = None
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить тест микрофона:\n{e}")
            self.refresh_devices(force_refresh=True)
            self.refresh_status()
            return False

    def _stop_meter(self):
        if self._meter_stream is not None:
            try:
                self._meter_stream.stop()
                self._meter_stream.close()
            except Exception:
                pass

            self._meter_stream = None

        with self._meter_lock:
            self._latest_level = 0
            self._calibration_active = False
            self._calibration_samples = []

        self.meter_bar.setValue(0)
        self.meter_state_label.setText("Тест микрофона: выключен")
        self.meter_hint_label.setText("Уровень сигнала пока не оценён.")
        self.test_mic_btn.setText("Проверить микрофон")

        self.meter_panel.setVisible(False)

        self.refresh_status()

    def _update_meter_ui(self):
        with self._meter_lock:
            level = self._latest_level

        self.meter_bar.setValue(level)

        cfg = settings_service.get_all()
        audio_cfg = cfg.get("audio", {})
        low = int(audio_cfg.get("meter_good_level_min", 18))
        high = int(audio_cfg.get("meter_good_level_max", 75))

        if level == 0:
            self.meter_hint_label.setText("Сигнал отсутствует.")
        elif level < low:
            self.meter_hint_label.setText("Сигнал слишком тихий. Во время записи будет применяться автоусиление.")
        elif level <= high:
            self.meter_hint_label.setText("Уровень сигнала нормальный для распознавания.")
        else:
            self.meter_hint_label.setText("Сигнал слишком высокий, возможны перегрузки.")

        if self._meter_stream is not None:
            self.refresh_status()

    def auto_calibrate(self):
        if not self._start_meter():
            return

        self.meter_panel.setVisible(True)
        self.meter_state_label.setText("Автонастройка: говорите обычной громкостью")
        self.meter_hint_label.setText(
            "В течение 5 секунд говорите обычной громкостью. "
            "Ассистент подберёт усиление и порог тишины."
        )

        with self._meter_lock:
            self._calibration_samples = []
            self._calibration_active = True

        self.auto_calibrate_btn.setEnabled(False)
        self.auto_calibrate_btn.setText("Слушаю...")

        QTimer.singleShot(5000, self._finish_auto_calibration)

    def _finish_auto_calibration(self):
        with self._meter_lock:
            samples = list(self._calibration_samples)
            self._calibration_active = False
            self._calibration_samples = []

        self.auto_calibrate_btn.setEnabled(True)
        self.auto_calibrate_btn.setText("Автонастройка")

        useful = [x for x in samples if x > 0]

        if not useful:
            QMessageBox.warning(
                self,
                "Автонастройка",
                "Не удалось услышать сигнал с микрофона. Проверьте устройство и попробуйте снова."
            )
            self.meter_state_label.setText("Автонастройка: не удалось услышать микрофон")
            self._stop_meter()
            return

        avg_level = sum(useful) / len(useful)
        peak_level = max(useful)

        recommended_gain = 1.0

        if avg_level < 12:
            recommended_gain = 2.5
        elif avg_level < 20:
            recommended_gain = 2.0
        elif avg_level < 32:
            recommended_gain = 1.5
        elif avg_level > 85:
            recommended_gain = 0.7
        elif avg_level > 70:
            recommended_gain = 0.85

        silence_threshold = 500
        if avg_level < 15:
            silence_threshold = 250
        elif avg_level < 25:
            silence_threshold = 350
        elif avg_level > 70:
            silence_threshold = 650

        self.input_gain_edit.setText(str(round(recommended_gain, 2)))
        self.silence_threshold_edit.setText(str(silence_threshold))

        def mutator(cfg: dict):
            cfg.setdefault("audio", {})
            cfg["audio"]["input_gain"] = recommended_gain
            cfg["audio"]["silence_threshold"] = silence_threshold
            cfg["audio"]["input_device_name"] = self._selected_mic_value
            cfg["audio"]["microphone_enabled"] = self.microphone_enabled_checkbox.isChecked()

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False

        self.meter_state_label.setText("Автонастройка завершена")
        self.meter_hint_label.setText(
            f"Средний уровень: {avg_level:.1f}%. "
            f"Пиковый уровень: {peak_level:.1f}%. "
            f"Усиление: {recommended_gain}. Порог тишины: {silence_threshold}."
        )

        self.refresh_status()
        self.save_bar.show_saved("Успешно настроено")

        QTimer.singleShot(900, self._stop_meter)

    def save_settings(self):
        state = self._capture_form_state()

        try:
            input_gain = float(state["input_gain"])
            max_record = float(state["max_record_seconds"])
            min_record = float(state["min_record_seconds"])
            silence_stop = float(state["silence_duration_stop_sec"])
            silence_threshold = int(state["silence_threshold"])
            rate = int(state["rate"])
            volume = float(state["volume"])
            heartbeat = int(state["heartbeat_interval_sec"])
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Проверьте числовые параметры в расширенных настройках:\n{e}")
            return

        def mutator(cfg: dict):
            cfg.setdefault("voice", {})
            cfg.setdefault("audio", {})

            cfg["voice"]["enabled"] = state["voice_enabled"]
            cfg["voice"]["rate"] = rate
            cfg["voice"]["volume"] = volume
            cfg["voice"]["heartbeat_interval_sec"] = heartbeat

            cfg["audio"]["microphone_enabled"] = state["microphone_enabled"]
            cfg["audio"]["input_device_name"] = state["input_device_name"]
            cfg["audio"]["output_device_name"] = state["output_device_name"]
            cfg["audio"]["input_gain"] = input_gain
            cfg["audio"]["max_record_seconds"] = max_record
            cfg["audio"]["min_record_seconds"] = min_record
            cfg["audio"]["silence_duration_stop_sec"] = silence_stop
            cfg["audio"]["silence_threshold"] = silence_threshold

        settings_service.update(mutator)

        self.config = settings_service.get_all()
        self._saved_form_state = self._capture_form_state()
        self._dirty = False

        self.refresh_status()
        self.save_bar.show_saved("Успешно настроено")

    def closeEvent(self, event):
        self._stop_meter()
        super().closeEvent(event)
