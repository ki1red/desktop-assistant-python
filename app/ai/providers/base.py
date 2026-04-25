class BaseAIProvider:
    def reply(self, user_text: str) -> str:
        raise NotImplementedError

    def refine_command(self, user_text: str, rules: dict | None = None) -> dict | None:
        return None

    def refine_dictation(self, user_text: str, rules: dict | None = None, context: list[str] | None = None) -> dict | None:
        return None