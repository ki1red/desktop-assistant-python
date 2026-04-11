import threading


class RuntimeControl:
    def __init__(self):
        self.cancel_event = threading.Event()
        self.busy_event = threading.Event()
        self.cancel_announced = threading.Event()

    def start_job(self):
        self.cancel_event.clear()
        self.cancel_announced.clear()
        self.busy_event.set()

    def finish_job(self):
        self.busy_event.clear()
        self.cancel_event.clear()
        self.cancel_announced.clear()

    def cancel_job(self):
        self.cancel_event.set()

    def is_busy(self) -> bool:
        return self.busy_event.is_set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def mark_cancel_announced(self) -> bool:
        """
        Возвращает True только один раз за одну операцию.
        """
        if self.cancel_announced.is_set():
            return False
        self.cancel_announced.set()
        return True


runtime_control = RuntimeControl()