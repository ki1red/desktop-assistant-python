from app.logger import get_logger
from app.settings_service import settings_service
from app.ai.providers.stub_provider import StubAIProvider
from app.ai.providers.ollama_provider import OllamaProvider

logger = get_logger("ai_gateway")


class AIGateway:
    def __init__(self):
        self.provider = self._build_provider()

    def _build_provider(self):
        cfg = settings_service.get_section("ai", {})
        provider_name = cfg.get("provider", "stub")

        logger.info("Выбор AI provider: %s", provider_name)

        if provider_name == "ollama":
            host = cfg.get("ollama_host", "http://localhost:11434")
            model = cfg.get("ollama_model", "gemma3:4b")
            chat_model = cfg.get("chat_ollama_model", model)

            try:
                provider = OllamaProvider(
                    host=host,
                    model=model,
                    chat_model=chat_model,
                )
                logger.info("Используется OllamaProvider.")
                return provider
            except Exception as e:
                logger.exception("Не удалось создать OllamaProvider: %s", e)

        logger.info("Используется StubAIProvider.")
        return StubAIProvider()

    def reload_provider(self):
        self.provider = self._build_provider()

    def ask(self, user_text: str) -> str:
        return self.provider.reply(user_text)

    def refine_command_text(self, text: str, rules: dict | None = None) -> dict | None:
        try:
            result = self.provider.refine_command(text, rules=rules)
            logger.info("AI refine_command result: %s", result)
            return result
        except Exception as e:
            logger.exception("Ошибка AI refine_command: %s", e)
            return None

    def refine_dictation_text(self, text: str, rules: dict | None = None, context: list[str] | None = None) -> dict | None:
        try:
            result = self.provider.refine_dictation(text, rules=rules, context=context)
            logger.info("AI refine_dictation result: %s", result)
            return result
        except Exception as e:
            logger.exception("Ошибка AI refine_dictation: %s", e)
            return None