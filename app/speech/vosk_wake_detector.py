import json
import threading
from pathlib import Path

import sounddevice as sd

from app.app_paths import BUNDLE_ROOT
from app.logger import get_logger
from app.settings_service import settings_service
from app.speech.recorder import resolve_input_device


logger = get_logger("vosk_wake_detector")

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
except Exception:
    Model = None
    KaldiRecognizer = None
    SetLogLevel = None


class VoskWakeDetectorError(RuntimeError):
    pass


def _normalize_text(text: str) -> str:
    value = (text or "").lower().replace("ё", "е")
    cleaned = []

    for ch in value:
        if ch.isalnum() or ch.isspace():
            cleaned.append(ch)
        else:
            cleaned.append(" ")

    return " ".join("".join(cleaned).split())


class VoskWakeDetector:
    """
    Отдельный wake-detector на Vosk.

    Он НЕ распознаёт основную команду.
    Его задача — только непрерывно слушать wake-фразу
    и после срабатывания вернуть управление background_service,
    который уже запускает обычную запись команды через Whisper pipeline.
    """

    def __init__(self):
        self._model = None
        self._model_lock = threading.RLock()
        self._loaded_model_path = None

        self.phrase = "ассистент"
        self.input_device_name = ""
        self.model_path_setting = "models/vosk-model-small-ru-0.22"
        self.sample_rate = 16000
        self.block_size = 4000

        self.reload_from_settings(settings_service.get_all())

        if callable(SetLogLevel):
            try:
                SetLogLevel(-1)
            except Exception:
                pass

    def reload_from_settings(self, config_snapshot: dict | None = None):
        cfg = config_snapshot or settings_service.get_all()
        assistant = cfg.get("assistant", {})
        audio = cfg.get("audio", {})

        self.phrase = (assistant.get("voice_activation_phrase", "ассистент") or "ассистент").strip()
        self.input_device_name = (audio.get("input_device_name", "") or "").strip()
        self.model_path_setting = (
            assistant.get("wake_vosk_model_path", "models/vosk-model-small-ru-0.22")
            or "models/vosk-model-small-ru-0.22"
        )
        self.sample_rate = int(assistant.get("wake_vosk_sample_rate", 16000) or 16000)
        self.block_size = int(assistant.get("wake_vosk_block_size", 4000) or 4000)

        self.sample_rate = max(8000, min(self.sample_rate, 48000))
        self.block_size = max(800, min(self.block_size, 16000))

    def _resolve_model_path(self) -> Path:
        raw_path = (self.model_path_setting or "").strip()
        if not raw_path:
            raw_path = "models/vosk-model-small-ru-0.22"

        path = Path(raw_path)
        if not path.is_absolute():
            path = (BUNDLE_ROOT / path).resolve()

        return path

    def _ensure_model_loaded(self):
        if Model is None or KaldiRecognizer is None:
            raise VoskWakeDetectorError(
                "Модуль vosk не установлен. Установите его командой: pip install vosk"
            )

        model_path = self._resolve_model_path()

        if not model_path.exists() or not model_path.is_dir():
            raise VoskWakeDetectorError(
                "Не найдена Vosk-модель для wake-listener. "
                f"Ожидается папка: {model_path}"
            )

        with self._model_lock:
            if self._model is not None and self._loaded_model_path == str(model_path):
                return

            logger.info("Загрузка Vosk-модели wake-listener: %s", model_path)
            self._model = Model(str(model_path))
            self._loaded_model_path = str(model_path)
            logger.info("Vosk-модель wake-listener загружена: %s", model_path)

    def _build_grammar(self) -> str:
        """
        Для wake-listener делаем максимально узкую грамматику:
        только полная wake-фраза.

        Это заметно снижает ложные срабатывания.
        """
        phrase = _normalize_text(self.phrase)
        grammar_items = [phrase] if phrase else []

        return json.dumps(grammar_items, ensure_ascii=False)

    def _create_recognizer(self):
        self._ensure_model_loaded()
        grammar = self._build_grammar()

        if grammar:
            return KaldiRecognizer(self._model, float(self.sample_rate), grammar)

        return KaldiRecognizer(self._model, float(self.sample_rate))

    def _is_strict_wake_match(self, payload: str) -> bool:
        """
        Wake-фраза считается найденной только если
        финальный результат Vosk строго совпадает с полной фразой.
        """
        if not payload:
            return False

        try:
            data = json.loads(payload)
        except Exception:
            return False

        text_value = _normalize_text(str(data.get("text") or "").strip())
        phrase_value = _normalize_text(self.phrase)

        if not text_value or not phrase_value:
            return False

        return text_value == phrase_value

    def wait_for_wake(
        self,
        stop_event: threading.Event,
        can_listen=None,
    ) -> bool:
        """
        Блокирующее ожидание wake-фразы.

        Возвращает True, если полная wake-фраза найдена.
        Возвращает False, если нужно выйти без срабатывания.
        """
        recognizer = self._create_recognizer()
        device_index, resolved_name = resolve_input_device(
            selected_name=self.input_device_name,
            allow_fallback=False,
            refresh=True,
        )

        logger.debug(
            "Wake-listener Vosk слушает устройство: %s (index=%s)",
            resolved_name,
            device_index,
        )

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            dtype="int16",
            channels=1,
            device=device_index,
        ) as stream:
            while not stop_event.is_set():
                if callable(can_listen) and not can_listen():
                    return False

                data, overflowed = stream.read(self.block_size)

                if overflowed:
                    logger.debug("Wake-listener Vosk: overflow входного буфера.")

                chunk = bytes(data)
                if not chunk:
                    continue

                # Срабатываем только по ФИНАЛЬНОМУ результату.
                # PartialResult намеренно игнорируем, чтобы
                # фраза "слушай ассистент" не триггерилась уже на слове "слушай".
                if recognizer.AcceptWaveform(chunk):
                    final_payload = recognizer.Result()

                    if self._is_strict_wake_match(final_payload):
                        return True

        return False