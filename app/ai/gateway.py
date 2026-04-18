from app.settings_service import settings_service
from app.ai.providers.stub_provider import StubAIProvider
from app.ai.providers.ollama_provider import OllamaProvider


class AIGateway:
    def __init__(self):
        self.config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)
        self.provider = self._build_provider()

    def _on_settings_changed(self, config_snapshot: dict):
        self.config = config_snapshot
        self.provider = self._build_provider()

    def _build_provider(self):
        ai_cfg = self.config.get("ai", {})
        provider_name = ai_cfg.get("provider", "stub")

        if provider_name == "ollama":
            host = ai_cfg.get("ollama_host", "http://localhost:11434")
            model = ai_cfg.get("ollama_model", "qwen2.5:7b")
            try:
                return OllamaProvider(host=host, model=model)
            except Exception:
                return StubAIProvider()

        return StubAIProvider()

    def ask(self, user_text: str) -> str:
        try:
            return self.provider.reply(user_text)
        except Exception as e:
            return f"Не удалось получить ответ от AI-провайдера: {e}"