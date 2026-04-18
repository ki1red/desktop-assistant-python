import json
import urllib.request
import urllib.error

from app.ai.providers.base import BaseAIProvider


class OllamaProvider(BaseAIProvider):
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

        # Важно: не использовать системные proxy для localhost
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _post_json(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.host}{endpoint}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            url=url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        with self.opener.open(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw)

    def reply(self, user_text: str) -> str:
        system_prompt = (
            "Ты локальный голосовой ассистент пользователя. "
            "Отвечай кратко, ясно и по делу. "
            "Если запрос похож на управляющую команду для компьютера, "
            "не утверждай, что уже выполнил её, а просто объясни или уточни."
        )

        chat_error = None

        try:
            response = self._post_json(
                "/api/chat",
                {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text},
                    ],
                    "stream": False,
                },
            )

            message = response.get("message", {})
            content = (message.get("content") or "").strip()
            if content:
                return content
        except Exception as e:
            chat_error = e

        try:
            response = self._post_json(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\nПользователь: {user_text}\nАссистент:",
                    "stream": False,
                },
            )

            content = (response.get("response") or "").strip()
            if content:
                return content

            if chat_error:
                return f"chat не сработал ({chat_error}), а generate не вернул текста."
            return "Локальная модель Ollama не вернула текстового ответа."

        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            if chat_error:
                return (
                    f"Ошибка Ollama.\n"
                    f"host={self.host}\n"
                    f"model={self.model}\n"
                    f"chat: {chat_error}\n"
                    f"generate HTTP {e.code}: {body or e.reason}"
                )
            return (
                f"Ошибка Ollama HTTP {e.code}.\n"
                f"host={self.host}\n"
                f"model={self.model}\n"
                f"{body or e.reason}"
            )
        except Exception as e:
            if chat_error:
                return (
                    f"Ошибка Ollama.\n"
                    f"host={self.host}\n"
                    f"model={self.model}\n"
                    f"chat: {chat_error}\n"
                    f"generate: {e}"
                )
            return f"Ошибка Ollama.\nhost={self.host}\nmodel={self.model}\n{e}"