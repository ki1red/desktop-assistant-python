import json
import re
import urllib.request
import urllib.error

from app.ai.providers.base import BaseAIProvider


def _extract_json_object(text: str) -> dict | None:
    if not text:
        return None

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None


class OllamaProvider(BaseAIProvider):
    def __init__(self, host: str, model: str, chat_model: str | None = None):
        self.host = host.rstrip("/")
        self.model = (model or "").strip()
        self.chat_model = (chat_model or model or "").strip()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _post_json(self, endpoint: str, payload: dict, timeout: int = 180) -> dict:
        url = f"{self.host}{endpoint}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            url=url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        with self.opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw)

    def _generate(self, prompt: str, model: str | None = None, timeout: int = 240) -> str:
        model_name = (model or self.chat_model or self.model).strip()

        response = self._post_json(
            "/api/generate",
            {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=timeout,
        )

        return (response.get("response") or "").strip()

    def reply(self, user_text: str) -> str:
        prompt = (
            "Ты локальный голосовой ассистент пользователя.\n"
            "Отвечай очень кратко, естественно и по делу.\n"
            "Максимум 2 коротких предложения.\n"
            "Если запрос похож на команду для компьютера, не утверждай, что уже выполнил её.\n\n"
            f"Пользователь: {user_text}\n"
            "Ассистент:"
        )

        try:
            content = self._generate(prompt, model=self.chat_model, timeout=240)
            if content:
                return content
            return "Модель не вернула текстового ответа."
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            return f"Ошибка Ollama HTTP {e.code}: {body or e.reason}"
        except Exception as e:
            return f"Ошибка обращения к Ollama: {e}"

    def refine_command(self, user_text: str, rules: dict | None = None) -> dict | None:
        rules = rules or {}

        prompt = f"""
    Ты помогаешь локальному Windows-ассистенту лучше понимать голосовые команды.

    Задача:
    1. Убрать лишние и вежливые слова.
    2. Исправить криво распознанные названия приложений, файлов, расширений и слов.
    3. Привести target к более понятному виду.
    4. Если команда относится к режимам ассистента, вернуть именно внутренний intent.
    5. Не выдумывать "человеческие" intent-ы. Используй только разрешённые значения ниже.

    Разрешённые значения intent_hint:
    - enable_chat_mode
    - disable_chat_mode
    - enable_dictation
    - disable_dictation
    - open_file
    - open_folder
    - generic_open
    - search_web
    - search_youtube
    - play_music_query
    - select_candidate
    - unknown
    - null

    Правила:
    - polite_words: {rules.get("polite_words", [])}
    - filler_words: {rules.get("filler_words", [])}
    - command_verbs: {rules.get("command_verbs", [])}
    - extension_aliases: {rules.get("extension_aliases", {})}

    Если команда звучит как:
    - "включи режим общения" -> intent_hint = "enable_chat_mode", target_hint = null
    - "выключи режим общения" -> intent_hint = "disable_chat_mode", target_hint = null
    - "включи диктовку" -> intent_hint = "enable_dictation", target_hint = null
    - "выключи диктовку" -> intent_hint = "disable_dictation", target_hint = null

    Текст пользователя:
    {user_text}

    Верни только JSON:
    {{
      "normalized_text": "...",
      "intent_hint": "... или null",
      "target_hint": "... или null",
      "entity_type_hint": "... или null",
      "comment": "...",
      "confidence": 0.0
    }}
    """.strip()

        try:
            response = self._generate(prompt, model=self.chat_model, timeout=120)
            data = _extract_json_object(response)
            if not data:
                return None

            return {
                "normalized_text": str(data.get("normalized_text") or "").strip(),
                "intent_hint": data.get("intent_hint"),
                "target_hint": data.get("target_hint"),
                "entity_type_hint": data.get("entity_type_hint"),
                "comment": data.get("comment"),
                "confidence": float(data.get("confidence") or 0.0),
            }
        except Exception:
            return None

    def refine_dictation(self, user_text: str, rules: dict | None = None, context: list[str] | None = None) -> dict | None:
        rules = rules or {}
        context = context or []

        prompt = f"""
Ты помогаешь локальному голосовому ассистенту обрабатывать диктовку.

Задача:
1. Нормализовать текст.
2. Превратить словесные обозначения знаков препинания в реальные знаки.
3. Исправить регистр и базовую пунктуацию.
4. Учитывать предыдущий контекст, если он есть.

Правила:
- dictation_replacements: {rules.get("dictation_replacements", {})}

Контекст:
{context}

Текущий текст:
{user_text}

Верни только JSON:
{{
  "normalized_text": "...",
  "comment": "...",
  "confidence": 0.0
}}
""".strip()

        try:
            response = self._generate(prompt, model=self.chat_model, timeout=120)
            data = _extract_json_object(response)
            if not data:
                return None

            return {
                "normalized_text": str(data.get("normalized_text") or "").strip(),
                "comment": data.get("comment"),
                "confidence": float(data.get("confidence") or 0.0),
            }
        except Exception:
            return None