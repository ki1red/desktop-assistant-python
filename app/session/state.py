class SessionState:
    def __init__(self):
        self.last_command = None
        self.last_resolved = None
        self.last_execution = None

    def remember(self, command, resolved, execution):
        self.last_command = command
        self.last_resolved = resolved
        self.last_execution = execution


session_state = SessionState()