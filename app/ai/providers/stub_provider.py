from app.ai.providers.base import BaseAIProvider


class StubAIProvider(BaseAIProvider):
    def reply(self, user_text: str) -> str:
        text = user_text.strip()
        low = text.lower()

        if not text:
            return "Я ничего не расслышал."

        if "блендер" in low:
            return "Похоже, ты говоришь про Blender. Позже сюда можно будет подключить внешний ИИ и полноценные инструменты."
        if "папк" in low or "файл" in low:
            return "Я могу обсудить это в режиме общения, а для точного открытия лучше использовать обычный командный режим."
        if "кто ты" in low:
            return "Я локальный ассистент. Сейчас у меня включён заготовочный режим общения."
        if "что ты умеешь" in low:
            return "Я умею выполнять локальные команды, искать в браузере, открывать музыку, работать с диктовкой и базово поддерживаю режим общения."

        return f"Я услышал: {text}. Сейчас это заготовка AI-режима. Позже сюда подключим внешний ИИ."