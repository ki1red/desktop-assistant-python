from app.settings_service import settings_service
from app.ai.providers.stub_provider import StubAIProvider
from app.ai.providers.ollama_provider import OllamaProvider
from app.logger import get_logger


logger = get_logger("ai_gateway")


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

        logger.info("Выбор AI provider: %s", provider_name)

        if provider_name == "ollama":
            host = ai_cfg.get("ollama_host", "http://localhost:11434")

            # Для chat-mode сначала берём быструю модель, если указана
            model = (
                ai_cfg.get("chat_ollama_model", "").strip()
                or ai_cfg.get("ollama_model", "qwen2.5:3b")
            )

            logger.info("Пробую Ollama provider: host=%s model=%s", host, model)

            try:
                provider = OllamaProvider(host=host, model=model)
                logger.info("Ollama provider успешно создан.")
                return provider
            except Exception as e:
                logger.exception("Не удалось создать Ollama provider, fallback на stub: %s", e)
                return StubAIProvider()

        logger.info("Используется StubAIProvider.")
        return StubAIProvider()

    def ask(self, user_text: str) -> str:
        try:
            logger.info("AI запрос: %s", user_text)
            reply = self.provider.reply(user_text)
            logger.info("AI ответ получен.")
            return reply
        except Exception as e:
            logger.exception("Ошибка AI provider: %s", e)
            return f"Не удалось получить ответ от AI-провайдера: {e}"