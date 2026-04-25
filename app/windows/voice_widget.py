import threading

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QCheckBox, QPushButton, QMessageBox, QComboBox,
    QLabel, QHBoxLayout, QProgressBar
)

from app.settings_service import settings_service
from app.speech.recorder import list_input_devices, list_output_devices


class VoiceSettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = settings_service.get_all()
        self.selected_mic_name = self.config["audio"].get("input_device_name", "")
        self.selected_output_name = self.config["audio"].get("output_device_name", "")

        self._meter_stream = None
        self._meter_lock = threading.Lock()
        self._latest_level = 0
        self._build_ui()
        self.refresh_devices()

    def _build_ui(self):
        voice = self.config["voice"]

        layout = QVBoxLayout(self)

        info = QLabel(
            "В этом разделе настраиваются голосовые ответы, устройство записи и устройство вывода."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.enabled_checkbox = QCheckBox("Включить голосовые ответы")
        self.enabled_checkbox.setChecked(voice.get("enabled", True))

        self.rate_edit = QLineEdit(str(voice.get("rate", 185)))
        self.volume_edit = QLineEdit(str(voice.get("volume", 1.0)))
        self.heartbeat_edit = QLineEdit(str(voice.get("heartbeat_interval_sec", 8)))

        self.mic_combo = QComboBox()
        self.output_combo = QComboBox()

        audio = self.config["audio"]

        self.input_gain_edit = QLineEdit(str(audio.get("input_gain", 1.0)))
        self.meter_hint_label = QLabel("Уровень сигнала пока не оценён.")
        self.auto_calibrate_btn = QPushButton("Подобрать усиление и порог")
        self.auto_calibrate_btn.clicked.connect(self.auto_calibrate)

        self.refresh_devices_btn = QPushButton("Обновить список устройств")
        self.refresh_devices_btn.clicked.connect(self.refresh_devices)

        self.meter_state_label = QLabel("Тест микрофона: выключен")
        self.meter_bar = QProgressBar()
        self.meter_bar.setRange(0, 100)
        self.meter_bar.setValue(0)

        self.toggle_meter_btn = QPushButton("Включить тест микрофона")
        self.toggle_meter_btn.clicked.connect(self.toggle_meter)

        form.addRow("", self.enabled_checkbox)
        form.addRow("Микрофон:", self.mic_combo)
        form.addRow("Устройство вывода:", self.output_combo)
        form.addRow("Программное усиление микрофона:", self.input_gain_edit)
        form.addRow("", self.refresh_devices_btn)
        form.addRow("Скорость речи:", self.rate_edit)
        form.addRow("Громкость:", self.volume_edit)
        form.addRow("Интервал фразы «ещё работаю» (сек):", self.heartbeat_edit)

        layout.addLayout(form)

        layout.addWidget(self.meter_state_label)
        layout.addWidget(self.meter_bar)
        layout.addWidget(self.meter_hint_label)
        layout.addWidget(self.auto_calibrate_btn)
        layout.addWidget(self.toggle_meter_btn)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_meter_ui)
        self.timer.start(100)

    def refresh_devices(self):
        self.mic_combo.clear()
        self.mic_combo.addItem("Не выбрано", "")

        for dev in list_input_devices():
            self.mic_combo.addItem(dev["name"], dev["name"])

        if self.selected_mic_name:
            idx = self.mic_combo.findData(self.selected_mic_name)
            self.mic_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.mic_combo.setCurrentIndex(0)

        self.output_combo.clear()
        self.output_combo.addItem("Не выбрано", "")

        for dev in list_output_devices():
            self.output_combo.addItem(dev["name"], dev["name"])

        if self.selected_output_name:
            idx = self.output_combo.findData(self.selected_output_name)
            self.output_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.output_combo.setCurrentIndex(0)

    def _find_selected_input_device_index(self):
        selected_name = self.mic_combo.currentData()
        if not selected_name:
            return None

        for dev in list_input_devices():
            if dev["name"] == selected_name:
                return dev["index"]

        return None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            return

        audio = indata.astype(np.float32)
        rms = float(np.sqrt(np.mean(np.square(audio))))

        cfg = settings_service.get_all()
        audio_cfg = cfg.get("audio", {})

        gain = float(self.input_gain_edit.text().strip() or "1.0")
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

        with self._meter_lock:
            self._latest_level = max(0, min(level, 100))

    def toggle_meter(self):
        if self._meter_stream is None:
            device_index = self._find_selected_input_device_index()
            if device_index is None:
                QMessageBox.warning(self, "Нет микрофона", "Сначала выбери микрофон.")
                return

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
                self.meter_state_label.setText("Тест микрофона: включён")
                self.toggle_meter_btn.setText("Выключить тест микрофона")
            except Exception as e:
                self._meter_stream = None
                QMessageBox.critical(self, "Ошибка", f"Не удалось запустить тест микрофона:\n{e}")
        else:
            self._stop_meter()

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

        self.meter_bar.setValue(0)
        self.meter_state_label.setText("Тест микрофона: выключен")
        self.toggle_meter_btn.setText("Включить тест микрофона")

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

    def save_settings(self):
        selected_mic = self.mic_combo.currentData() or ""
        selected_output = self.output_combo.currentData() or ""

        def mutator(cfg: dict):
            cfg["voice"]["enabled"] = self.enabled_checkbox.isChecked()
            cfg["voice"]["rate"] = int(self.rate_edit.text().strip())
            cfg["voice"]["volume"] = float(self.volume_edit.text().strip())
            cfg["voice"]["heartbeat_interval_sec"] = int(self.heartbeat_edit.text().strip())
            cfg["audio"]["input_device_name"] = selected_mic
            cfg["audio"]["output_device_name"] = selected_output
            cfg["audio"]["input_gain"] = float(self.input_gain_edit.text().strip())

        settings_service.update(mutator)
        self.config = settings_service.get_all()
        self.selected_mic_name = self.config["audio"].get("input_device_name", "")
        self.selected_output_name = self.config["audio"].get("output_device_name", "")
        QMessageBox.information(self, "Готово", "Голосовые настройки и устройства сохранены.")

    def auto_calibrate(self):
        try:
            level = self.meter_bar.value()

            if level == 0:
                QMessageBox.warning(self, "Калибровка", "Сейчас нет сигнала с микрофона.")
                return

            recommended_gain = 1.0

            if level < 15:
                recommended_gain = 2.0
            elif level < 25:
                recommended_gain = 1.5
            elif level > 85:
                recommended_gain = 0.7
            elif level > 70:
                recommended_gain = 0.85

            silence_threshold = 500
            if level < 15:
                silence_threshold = 250
            elif level < 25:
                silence_threshold = 350
            elif level > 70:
                silence_threshold = 650

            self.input_gain_edit.setText(str(round(recommended_gain, 2)))

            def mutator(cfg: dict):
                cfg["audio"]["input_gain"] = recommended_gain
                cfg["audio"]["silence_threshold"] = silence_threshold

            settings_service.update(mutator)

            QMessageBox.information(
                self,
                "Калибровка завершена",
                f"Рекомендуемое усиление: {recommended_gain}\n"
                f"Рекомендуемый порог тишины: {silence_threshold}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выполнить автокалибровку:\n{e}")

    def closeEvent(self, event):
        self._stop_meter()
        super().closeEvent(event)