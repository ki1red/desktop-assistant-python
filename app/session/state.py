class SessionState:
    """
    Состояние последней команды.

    pending_* поля оставлены для совместимости со старым кодом,
    но новые подтверждения и выбор кандидатов отключены.
    """

    def __init__(self):
        self.last_command = None
        self.last_resolved = None
        self.last_execution = None

        # Старые поля. Теперь всегда очищаются и не используются новой логикой.
        self.pending_deep_search_command = None
        self.pending_candidates = None
        self.pending_selection_command = None

    def remember(self, command, resolved, execution):
        """
        Запоминает последнее выполненное действие.
        """
        self.last_command = command
        self.last_resolved = resolved
        self.last_execution = execution

    def set_pending_deep_search(self, command):
        """
        Совместимая заглушка.

        Раньше здесь сохранялся запрос на глубокий поиск,
        чтобы пользователь сказал "да" или "нет".
        Теперь такие подтверждения отключены.
        """
        self.pending_deep_search_command = None

    def clear_pending_deep_search(self):
        """
        Очищает старое состояние глубокого поиска.
        """
        self.pending_deep_search_command = None

    def set_pending_candidates(self, command, candidates):
        """
        Совместимая заглушка.

        Раньше здесь сохранялись кандидаты для выбора
        "первый/второй/третий". Теперь resolver выбирает первый сам.
        """
        self.pending_selection_command = None
        self.pending_candidates = None

    def clear_pending_candidates(self):
        """
        Очищает старое состояние выбора кандидатов.
        """
        self.pending_selection_command = None
        self.pending_candidates = None

    def clear_pending_all(self):
        """
        Очищает все старые pending-состояния.
        """
        self.clear_pending_deep_search()
        self.clear_pending_candidates()


session_state = SessionState()