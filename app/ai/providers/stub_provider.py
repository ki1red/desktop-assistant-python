from app.ai.providers.base import BaseAIProvider


class StubAIProvider(BaseAIProvider):
    def reply(self, user_text: str) -> str:
        return "ИИ сейчас недоступен. Используется безопасный режим без интеллектуальной обработки."

    def refine_command(self, user_text: str, rules: dict | None = None) -> dict | None:
        return {
            "normalized_text": user_text.strip(),
            "intent_hint": None,
            "target_hint": None,
            "entity_type_hint": None,
            "comment": "stub",
            "confidence": 0.0
        }

    def refine_dictation(self, user_text: str, rules: dict | None = None, context: list[str] | None = None) -> dict | None:
        return {
            "normalized_text": user_text.strip(),
            "comment": "stub",
            "confidence": 0.0
        }