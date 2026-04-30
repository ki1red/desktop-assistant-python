import threading
from copy import deepcopy

from app.config_loader import ConfigLoader
from app.logger import get_logger


logger = get_logger("settings_service")


class SettingsService:
    def __init__(self):
        self._loader = ConfigLoader()
        self._lock = threading.RLock()
        self._subscribers = []
        self._config = self._loader.get()

    def get_all(self) -> dict:
        with self._lock:
            return deepcopy(self._config)

    def get_section(self, section_name: str, default=None):
        with self._lock:
            return deepcopy(self._config.get(section_name, default))

    def reload(self):
        """
        Полностью перечитывает пользовательский settings.json через ConfigLoader.

        Важно:
        обновлять нужно именно _loader и _config, потому что остальные методы
        работают с приватными полями.
        """
        with self._lock:
            self._loader = ConfigLoader()
            self._config = self._loader.get()
            snapshot = deepcopy(self._config)

        logger.info("Конфиг перезагружен.")
        self._notify(snapshot)

    def update(self, mutate_fn):
        """
        Сохраняет изменённый конфиг и сразу приводит in-memory snapshot
        к нормализованному виду через ConfigLoader.

        Это важно для миграций и мягкой очистки устаревших ключей:
        mutate_fn может добавить старые поля для совместимости,
        но после save() в памяти должен остаться уже нормализованный конфиг.
        """
        with self._lock:
            config_copy = deepcopy(self._config)
            mutate_fn(config_copy)
            self._loader.save(config_copy)

            # Берём именно нормализованную версию после save(),
            # а не исходный config_copy до пост-обработки.
            self._config = self._loader.get()
            snapshot = deepcopy(self._config)

        logger.info("Конфиг обновлён и сохранён.")
        self._notify(snapshot)

    def subscribe(self, callback):
        with self._lock:
            self._subscribers.append(callback)

    def _notify(self, config_snapshot: dict):
        for callback in list(self._subscribers):
            try:
                callback(config_snapshot)
            except Exception as e:
                logger.exception("Ошибка подписчика настроек: %s", e)


settings_service = SettingsService()