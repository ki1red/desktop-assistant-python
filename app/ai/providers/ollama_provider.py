import json
import urllib.request
import urllib.error

from app.ai.providers.base import BaseAIProvider


class OllamaProvider(BaseAIProvider):
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model
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
            response = self._post_json(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=240,
            )

            content = (response.get("response") or "").strip()
            if content:
                return content

            return "Модель не вернула текстового ответа."
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            return (
                f"Ошибка Ollama HTTP {e.code}.\n"
                f"host={self.host}\n"
                f"model={self.model}\n"
                f"{body or e.reason}"
            )
        except Exception as e:
            return (
                f"Ошибка Ollama.\n"
                f"host={self.host}\n"
                f"model={self.model}\n"
                f"{e}"
            )