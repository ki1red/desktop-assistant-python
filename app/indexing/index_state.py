import threading


class IndexState:
    def __init__(self):
        self._lock = threading.RLock()
        self._is_running = False
        self._message = "Индексация не выполняется."
        self._indexed_count = 0

    def start(self, message="Идёт индексация файлов..."):
        with self._lock:
            self._is_running = True
            self._message = message

    def update(self, message=None, indexed_count=None):
        with self._lock:
            if message is not None:
                self._message = message
            if indexed_count is not None:
                self._indexed_count = indexed_count

    def finish(self, message="Индексация завершена."):
        with self._lock:
            self._is_running = False
            self._message = message

    def snapshot(self):
        with self._lock:
            return {
                "is_running": self._is_running,
                "message": self._message,
                "indexed_count": self._indexed_count,
            }


index_state = IndexState()