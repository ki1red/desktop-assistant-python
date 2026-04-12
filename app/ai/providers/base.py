class BaseAIProvider:
    def reply(self, user_text: str) -> str:
        raise NotImplementedError