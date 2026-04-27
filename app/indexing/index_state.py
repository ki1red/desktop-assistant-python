import threading
from datetime import datetime


class IndexState:
    def __init__(self):
        self._lock = threading.RLock()
        self._is_running = False
        self._status = "idle"
        self._message = "Индексация не выполняется."
        self._indexed_count = 0
        self._last_error = ""
        self._started_at = ""
        self._finished_at = ""

    def start(self, message="Идёт индексация файлов..."):
        with self._lock:
            self._is_running = True
            self._status = "building"
            self._message = message
            self._indexed_count = 0
            self._last_error = ""
            self._started_at = datetime.now().isoformat(timespec="seconds")
            self._finished_at = ""

    def update(self, message=None, indexed_count=None):
        with self._lock:
            if message is not None:
                self._message = message
            if indexed_count is not None:
                self._indexed_count = int(indexed_count)

    def finish(self, message="Индексация завершена.", indexed_count=None):
        with self._lock:
            self._is_running = False
            self._status = "ready"
            self._message = message
            if indexed_count is not None:
                self._indexed_count = int(indexed_count)
            self._last_error = ""
            self._finished_at = datetime.now().isoformat(timespec="seconds")

    def fail(self, message="Ошибка индексации.", error: str = ""):
        with self._lock:
            self._is_running = False
            self._status = "failed"
            self._message = message
            self._last_error = error or message
            self._finished_at = datetime.now().isoformat(timespec="seconds")

    def mark_missing(self, message="Индекс отсутствует. Требуется восстановление."):
        with self._lock:
            if self._is_running:
                return
            self._status = "missing"
            self._message = message
            self._indexed_count = 0

    def snapshot(self):
        with self._lock:
            return {
                "is_running": self._is_running,
                "status": self._status,
                "message": self._message,
                "indexed_count": self._indexed_count,
                "last_error": self._last_error,
                "started_at": self._started_at,
                "finished_at": self._finished_at,
            }


index_state = IndexState()