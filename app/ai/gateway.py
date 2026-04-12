from app.settings_service import settings_service
from app.ai.providers.stub_provider import StubAIProvider


class AIGateway:
    def __init__(self):
        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)
        self.provider = self._build_provider()

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot
        self.provider = self._build_provider()

    def _build_provider(self):
        provider_name = self.config.get("ai", {}).get("provider", "stub")
        if provider_name == "stub":
            return StubAIProvider()

        return StubAIProvider()

    def ask(self, user_text: str) -> str:
        return self.provider.reply(user_text)