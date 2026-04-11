class SessionState:
    def __init__(self):
        self.last_command = None
        self.last_resolved = None
        self.last_execution = None
        self.pending_deep_search_command = None
        self.pending_candidates = None
        self.pending_selection_command = None

    def remember(self, command, resolved, execution):
        self.last_command = command
        self.last_resolved = resolved
        self.last_execution = execution

    def set_pending_deep_search(self, command):
        self.pending_deep_search_command = command

    def clear_pending_deep_search(self):
        self.pending_deep_search_command = None

    def set_pending_candidates(self, command, candidates):
        self.pending_selection_command = command
        self.pending_candidates = candidates

    def clear_pending_candidates(self):
        self.pending_selection_command = None
        self.pending_candidates = None


session_state = SessionState()