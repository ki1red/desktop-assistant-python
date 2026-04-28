import threading
import time
import uuid
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from app.settings_service import settings_service
from app.logger import get_logger


logger = get_logger("recorder")


class MicrophoneSelectionError(RuntimeError):
    pass


class NoMicrophoneSignalError(RuntimeError):
    pass


MIC_INCLUDE_KEYWORDS = [
    "microphone",
    "microph",
    "mic",
    "микрофон",
    "гарнитура",
    "headset",
    "webcam",
    "камера",
    "array",
    "массив",
    "fifine",
    "maono",
    "yeti",
    "rode",
    "hyperx",
    "razer seiren",
    "logitech",
    "blue snowball",
]

MIC_EXCLUDE_KEYWORDS = [
    "stereo mix",
    "what u hear",
    "wave out",
    "loopback",
    "virtual",
    "cable output",
    "cable input",
    "output",
    "speaker",
    "speakers",
    "динамик",
    "динамики",
    "колонки",
    "monitor",
    "наушники",
    "headphones",
    "headphone",
    "hdmi",
    "display audio",
    "nvidia",
    "amd high definition",
    "realtek digital output",
    "primary sound capture driver",
    "sound mapper",
    "mapper",
]

OUTPUT_INCLUDE_KEYWORDS = [
    "speaker", "speakers", "headphones", "headset",
    "науш", "динамик", "колонки", "realtek", "hdmi",
    "display audio", "usb audio"
]

OUTPUT_EXCLUDE_KEYWORDS = [
    "microphone", "mic", "микрофон", "input", "вход",
    "loopback", "stereo mix", "virtual cable"
]


_AUDIO_DEVICE_REFRESH_LOCK = threading.RLock()
_LAST_AUDIO_DEVICE_REFRESH_MONO = 0.0


def refresh_audio_devices(force: bool = False, min_interval_sec: float = 5.0) -> bool:
    """
    Принудительно обновляет список аудиоустройств PortAudio/sounddevice.

    Это помогает в ситуации, когда приложение стартовало раньше,
    чем Windows успела поднять USB-микрофон.
    """
    global _LAST_AUDIO_DEVICE_REFRESH_MONO

    now = time.monotonic()

    with _AUDIO_DEVICE_REFRESH_LOCK:
        if not force and (now - _LAST_AUDIO_DEVICE_REFRESH_MONO) < min_interval_sec:
            return False

        _LAST_AUDIO_DEVICE_REFRESH_MONO = now

        try:
            terminate = getattr(sd, "_terminate", None)
            initialize = getattr(sd, "_initialize", None)

            if callable(terminate) and callable(initialize):
                terminate()
                initialize()
                logger.info("Список аудиоустройств обновлён через PortAudio reinitialize.")
                return True

            # Фолбэк для версий sounddevice без приватных методов.
            sd.query_devices()
            logger.info("Список аудиоустройств обновлён через query_devices fallback.")
            return True

        except Exception as e:
            logger.warning("Не удалось принудительно обновить список аудиоустройств: %s", e)
            return False


def _normalize_device_name(device_name: str) -> str:
    value = (device_name or "").lower().replace("ё", "е")
    for ch in ["(", ")", "[", "]", "{", "}", ",", ";", ":"]:
        value = value.replace(ch, " ")
    value = " ".join(value.split())
    return value


def _device_name_matches(selected_name: str, real_name: str) -> bool:
    """
    Сравнивает сохранённое имя устройства с реальным.

    Поддерживает:
    - точное совпадение;
    - частичное совпадение;
    - случай, когда Windows/Qt обрезали имя устройства.
    """
    selected = _normalize_device_name(selected_name)
    real = _normalize_device_name(real_name)

    if not selected or not real:
        return False

    return selected == real or selected in real or real in selected


def _looks_like_microphone(device_name: str) -> bool:
    """
    Фильтрует устройства ввода для UI.

    В список микрофонов не должны попадать:
    - Stereo Mix;
    - loopback/virtual cable;
    - динамики/HDMI/monitor audio;
    - слишком общие Realtek/Audio/Input без признаков микрофона.

    Важно:
    не используем слишком широкие слова вроде "audio", "input", "realtek",
    потому что они добавляют в список лишние устройства.
    """
    name = _normalize_device_name(device_name)

    if not name:
        return False

    if any(bad in name for bad in MIC_EXCLUDE_KEYWORDS):
        return False

    if any(good in name for good in MIC_INCLUDE_KEYWORDS):
        return True

    # Частый вариант Windows: "Microphone Array ..."
    if "микрофонный массив" in name:
        return True

    # Не пропускаем просто "usb audio", "realtek audio", "input device".
    return False


def _looks_like_output_device(device_name: str) -> bool:
    name = (device_name or "").lower()

    if any(bad in name for bad in OUTPUT_EXCLUDE_KEYWORDS):
        return False

    if any(good in name for good in OUTPUT_INCLUDE_KEYWORDS):
        return True

    return True

def _deduplicate_audio_devices(devices: list[dict]) -> list[dict]:
    """
    Убирает дубликаты устройств по нормализованному имени.

    На Windows одно и то же устройство может показываться через разные host API.
    Для пользователя это выглядит как мусор в списке.
    """
    result = []
    seen = set()

    for dev in devices:
        name = dev.get("name", "")
        key = _normalize_device_name(name)

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(dev)

    return result

def _query_devices_safe(refresh: bool = False):
    if refresh:
        refresh_audio_devices(force=False)

    try:
        return sd.query_devices()
    except Exception as e:
        logger.warning("sd.query_devices() failed: %s. Пробую обновить PortAudio.", e)
        refresh_audio_devices(force=True)

    return sd.query_devices()


def list_input_devices(refresh: bool = False) -> list[dict]:
    devices = _query_devices_safe(refresh=refresh)
    result = []

    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) <= 0:
            continue

        name = dev.get("name", "")
        if not _looks_like_microphone(name):
            continue

        result.append({
            "index": idx,
            "name": name,
            "channels": dev.get("max_input_channels", 0),
            "default_samplerate": dev.get("default_samplerate", 16000),
        })

    return _deduplicate_audio_devices(result)


def list_output_devices(refresh: bool = False) -> list[dict]:
    devices = _query_devices_safe(refresh=refresh)
    result = []

    for idx, dev in enumerate(devices):
        if dev.get("max_output_channels", 0) <= 0:
            continue

        name = dev["name"]
        if not _looks_like_output_device(name):
            continue

        result.append({
            "index": idx,
            "name": name,
            "channels": dev.get("max_output_channels", 0),
            "default_samplerate": dev.get("default_samplerate", 16000),
        })

    return result


def _pick_selected_input_device(devices: list[dict], selected_name: str) -> dict | None:
    selected_name = (selected_name or "").strip()
    if not selected_name:
        return None

    for dev in devices:
        if dev["name"] == selected_name:
            return dev

    for dev in devices:
        if _device_name_matches(selected_name, dev["name"]):
            return dev

    return None


def _pick_default_input_device(devices: list[dict]) -> dict | None:
    if not devices:
        return None

    try:
        default_device = sd.default.device

        if isinstance(default_device, (tuple, list)):
            default_input_index = default_device[0]
        else:
            default_input_index = default_device

        if default_input_index is not None and int(default_input_index) >= 0:
            for dev in devices:
                if int(dev["index"]) == int(default_input_index):
                    return dev

    except Exception as e:
        logger.debug("Не удалось определить default input device: %s", e)

    return devices[0]


def _save_resolved_input_device_if_changed(old_name: str, new_name: str):
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()

    if not new_name or old_name == new_name:
        return

    try:
        def mutator(cfg: dict):
            cfg.setdefault("audio", {})
            current = (cfg["audio"].get("input_device_name", "") or "").strip()

            if current == old_name:
                cfg["audio"]["input_device_name"] = new_name

        settings_service.update(mutator)
        logger.info("Выбранный микрофон обновлён в настройках: %r -> %r", old_name, new_name)

    except Exception as e:
        logger.warning("Не удалось сохранить обновлённый микрофон в settings.json: %s", e)


def resolve_input_device(
    selected_name: str | None = None,
    allow_fallback: bool = True,
    refresh: bool = True,
) -> tuple[int, str]:
    """
    Находит индекс микрофона.

    Логика:
    - сначала ищем выбранный микрофон;
    - если не нашли, обновляем список устройств;
    - если всё ещё не нашли, берём default input / первый доступный микрофон.
    """
    selected_name = (selected_name or "").strip()

    devices = list_input_devices(refresh=False)
    selected_device = _pick_selected_input_device(devices, selected_name)

    if selected_device is None and refresh:
        devices = list_input_devices(refresh=True)
        selected_device = _pick_selected_input_device(devices, selected_name)

    if not devices:
        raise MicrophoneSelectionError(
            "На компьютере не обнаружены устройства записи. "
            "Проверьте подключение микрофона и разрешения Windows."
        )

    if selected_device is not None:
        _save_resolved_input_device_if_changed(selected_name, selected_device["name"])
        return selected_device["index"], selected_device["name"]

    if not allow_fallback:
        raise MicrophoneSelectionError(
            "Выбранный микрофон недоступен. Проверьте устройство во вкладке «Аудио»."
        )

    fallback = _pick_default_input_device(devices)

    if fallback is None:
        raise MicrophoneSelectionError(
            "Не удалось выбрать устройство записи. Проверьте микрофон во вкладке «Аудио»."
        )

    logger.warning(
        "Выбранный микрофон недоступен: %r. Использую fallback microphone: %r",
        selected_name,
        fallback["name"],
    )

    _save_resolved_input_device_if_changed(selected_name, fallback["name"])
    return fallback["index"], fallback["name"]


def _resolve_input_device(selected_name: str) -> tuple[int, str]:
    """
    Старое имя функции оставлено для совместимости.
    """
    return resolve_input_device(
        selected_name=selected_name,
        allow_fallback=True,
        refresh=True,
    )


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int, channels: int):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.astype(np.int16).tobytes())


def _apply_gain(data: np.ndarray, gain: float) -> np.ndarray:
    amplified = data.astype(np.float32) * float(gain)
    amplified = np.clip(amplified, -32768, 32767)
    return amplified.astype(np.int16)


def _rms(data: np.ndarray) -> float:
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(data.astype(np.float32)))))


def _post_normalize_audio(audio: np.ndarray, target_rms: float, max_gain: float) -> tuple[np.ndarray, float]:
    current_rms = _rms(audio)
    if current_rms <= 1.0:
        return audio, 1.0

    gain = target_rms / current_rms
    gain = max(1.0, min(float(max_gain), float(gain)))

    if gain <= 1.05:
        return audio, 1.0

    normalized = _apply_gain(audio, gain)
    return normalized, gain


def record_audio_to_wav() -> str:
    cfg = settings_service.get_all()
    audio_cfg = cfg["audio"]
    paths_cfg = cfg["paths"]

    if not bool(audio_cfg.get("microphone_enabled", True)):
        raise MicrophoneSelectionError(
            "Использование микрофона отключено в настройках. Включите микрофон во вкладке «Аудио»."
        )

    sample_rate = int(audio_cfg.get("sample_rate", 16000))
    channels = int(audio_cfg.get("channels", 1))
    chunk_size = int(audio_cfg.get("chunk_size", 1024))
    max_record_seconds = float(audio_cfg.get("max_record_seconds", 12))
    min_record_seconds = float(audio_cfg.get("min_record_seconds", 0.8))
    silence_duration_stop_sec = float(audio_cfg.get("silence_duration_stop_sec", 1.0))
    silence_threshold = int(audio_cfg.get("silence_threshold", 500))
    selected_device_name = audio_cfg.get("input_device_name", "")

    input_gain = float(audio_cfg.get("input_gain", 1.0))
    auto_gain_enabled = bool(audio_cfg.get("auto_input_gain_enabled", True))
    auto_gain_target_rms = float(audio_cfg.get("auto_gain_target_rms", 2200))
    max_auto_gain = float(audio_cfg.get("max_auto_gain", 10.0))
    no_signal_rms_threshold = float(audio_cfg.get("no_signal_rms_threshold", 120))

    temp_dir = Path(paths_cfg["temp_dir"])
    temp_dir.mkdir(parents=True, exist_ok=True)

    device_index, resolved_name = resolve_input_device(
        selected_name=selected_device_name,
        allow_fallback=True,
        refresh=True,
    )
    logger.info("Используется устройство записи: %s (index=%s)", resolved_name, device_index)

    frames = []
    total_duration = 0.0
    silence_duration = 0.0

    current_gain = max(0.1, input_gain)
    max_raw_rms = 0.0
    max_adjusted_rms = 0.0
    signal_detected = False

    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        blocksize=chunk_size,
        dtype="int16",
        device=device_index,
    ) as stream:
        while total_duration < max_record_seconds:
            data, overflowed = stream.read(chunk_size)

            if overflowed:
                logger.warning("Переполнение входного аудиобуфера.")

            raw_rms = _rms(data)
            max_raw_rms = max(max_raw_rms, raw_rms)

            if auto_gain_enabled:
                if raw_rms > 1.0:
                    desired_gain = auto_gain_target_rms / raw_rms
                    desired_gain = max(1.0, min(max_auto_gain, desired_gain))
                    current_gain = 0.7 * current_gain + 0.3 * desired_gain
                else:
                    current_gain = min(max_auto_gain, current_gain * 1.4)

            adjusted = _apply_gain(data, current_gain)
            adjusted_rms = _rms(adjusted)
            max_adjusted_rms = max(max_adjusted_rms, adjusted_rms)

            if adjusted_rms >= no_signal_rms_threshold:
                signal_detected = True

            frames.append(adjusted.copy())

            block_duration = len(adjusted) / sample_rate
            total_duration += block_duration

            if total_duration >= min_record_seconds and adjusted_rms < silence_threshold:
                silence_duration += block_duration
                if silence_duration >= silence_duration_stop_sec:
                    break
            else:
                silence_duration = 0.0

    if not frames:
        raise RuntimeError("Не удалось записать аудио.")

    audio = np.concatenate(frames, axis=0)

    audio, post_gain = _post_normalize_audio(audio, auto_gain_target_rms, max_auto_gain)
    final_rms = _rms(audio)

    logger.info(
        "Итог записи: raw_rms_max=%.2f adjusted_rms_max=%.2f final_rms=%.2f current_gain=%.2f post_gain=%.2f",
        max_raw_rms,
        max_adjusted_rms,
        final_rms,
        current_gain,
        post_gain,
    )

    if not signal_detected and final_rms < no_signal_rms_threshold:
        raise NoMicrophoneSignalError(
            "На выбранном микрофоне не обнаружен сигнал. "
            "Проверьте выключение микрофона, расстояние до него или уровень записи в системе."
        )

    wav_path = temp_dir / f"record_{uuid.uuid4().hex}.wav"
    _write_wav(wav_path, audio, sample_rate, channels)

    logger.info("Аудио записано: %s", wav_path)
    return str(wav_path)


def record_wake_audio_to_wav(max_seconds: float | None = None) -> str:
    """
    Короткая запись для режима голосовой активации.
    """
    cfg = settings_service.get_all()
    audio_cfg = cfg["audio"]
    paths_cfg = cfg["paths"]
    assistant_cfg = cfg.get("assistant", {})

    if not bool(audio_cfg.get("microphone_enabled", True)):
        raise MicrophoneSelectionError(
            "Использование микрофона отключено в настройках. Включите микрофон во вкладке «Аудио»."
        )

    sample_rate = int(audio_cfg.get("sample_rate", 16000))
    channels = int(audio_cfg.get("channels", 1))
    chunk_size = int(audio_cfg.get("chunk_size", 1024))
    selected_device_name = audio_cfg.get("input_device_name", "")

    input_gain = float(audio_cfg.get("input_gain", 1.0))
    auto_gain_enabled = bool(audio_cfg.get("auto_input_gain_enabled", True))
    auto_gain_target_rms = float(audio_cfg.get("auto_gain_target_rms", 2200))
    max_auto_gain = float(audio_cfg.get("max_auto_gain", 10.0))

    wake_seconds = float(
        max_seconds
        if max_seconds is not None
        else assistant_cfg.get("wake_record_seconds", 1.8)
    )
    wake_seconds = max(0.8, min(wake_seconds, 4.0))

    temp_dir = Path(paths_cfg["temp_dir"])
    temp_dir.mkdir(parents=True, exist_ok=True)

    device_index, resolved_name = resolve_input_device(
        selected_name=selected_device_name,
        allow_fallback=True,
        refresh=True,
    )

    frames = []
    total_duration = 0.0
    current_gain = max(0.1, input_gain)

    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        blocksize=chunk_size,
        dtype="int16",
        device=device_index,
    ) as stream:
        while total_duration < wake_seconds:
            data, overflowed = stream.read(chunk_size)

            if overflowed:
                logger.debug("Wake-аудио: переполнение входного аудиобуфера.")

            raw_rms = _rms(data)

            if auto_gain_enabled:
                if raw_rms > 1.0:
                    desired_gain = auto_gain_target_rms / raw_rms
                    desired_gain = max(1.0, min(max_auto_gain, desired_gain))
                    current_gain = 0.7 * current_gain + 0.3 * desired_gain
                else:
                    current_gain = min(max_auto_gain, current_gain * 1.4)

            adjusted = _apply_gain(data, current_gain)
            frames.append(adjusted.copy())

            block_duration = len(adjusted) / sample_rate
            total_duration += block_duration

    if not frames:
        raise RuntimeError("Не удалось записать wake-аудио.")

    audio = np.concatenate(frames, axis=0)
    audio, _post_gain = _post_normalize_audio(audio, auto_gain_target_rms, max_auto_gain)

    wav_path = temp_dir / f"wake_{uuid.uuid4().hex}.wav"
    _write_wav(wav_path, audio, sample_rate, channels)

    logger.debug("Wake-аудио записано: %s device=%s", wav_path, resolved_name)
    return str(wav_path)


def delete_temp_file(path: str | None):
    if not path:
        return

    try:
        p = Path(path)
        if p.exists():
            p.unlink()
            logger.info("Временный аудиофайл удалён: %s", p)
    except Exception as e:
        logger.warning("Не удалось удалить временный файл %s: %s", path, e)


def cleanup_old_temp_files():
    cfg = settings_service.get_all()
    temp_cfg = cfg.get("temp_cleanup", {})
    paths_cfg = cfg.get("paths", {})

    if not temp_cfg.get("delete_old_temp_on_startup", True):
        logger.info("Очистка старых temp-файлов отключена настройкой.")
        return

    temp_dir = Path(paths_cfg.get("temp_dir", "temp"))
    max_age_hours = float(temp_cfg.get("max_temp_age_hours", 24))

    if not temp_dir.exists():
        logger.info("Папка temp не существует, очистка не требуется: %s", temp_dir)
        return

    now = time.time()
    max_age_seconds = max_age_hours * 3600
    deleted_count = 0

    for item in temp_dir.iterdir():
        if not item.is_file():
            continue

        try:
            age = now - item.stat().st_mtime
            if age > max_age_seconds:
                item.unlink()
                deleted_count += 1
        except Exception as e:
            logger.warning("Не удалось очистить временный файл %s: %s", item, e)

    logger.info(
        "Очистка temp завершена: dir=%s deleted=%s max_age_hours=%s",
        temp_dir,
        deleted_count,
        max_age_hours,
    )