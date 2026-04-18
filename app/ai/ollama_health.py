import json
import urllib.request
import urllib.error


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _post_json(host: str, endpoint: str, payload: dict) -> dict:
    url = f"{host.rstrip('/')}{endpoint}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with _OPENER.open(req, timeout=180) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)


def check_ollama_connection(host: str, model: str) -> tuple[bool, str]:
    host = (host or "").strip()
    model = (model or "").strip()

    if not host:
        return False, "Не указан Ollama host."

    if not model:
        return False, "Не выбрана модель Ollama."

    chat_error = None

    try:
        response = _post_json(
            host,
            "/api/chat",
            {
                "model": model,
                "messages": [{"role": "user", "content": "Привет"}],
                "stream": False,
            },
        )
        message = response.get("message", {})
        content = (message.get("content") or "").strip()
        if content:
            return True, f"Ollama доступна. Модель отвечает через chat: {model}"
    except Exception as e:
        chat_error = e

    try:
        response = _post_json(
            host,
            "/api/generate",
            {
                "model": model,
                "prompt": "Привет",
                "stream": False,
            },
        )
        content = (response.get("response") or "").strip()
        if content:
            if chat_error:
                return True, f"Ollama доступна. chat не сработал ({chat_error}), но generate работает: {model}"
            return True, f"Ollama доступна. Модель отвечает через generate: {model}"
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        if chat_error:
            return False, (
                f"host={host}\n"
                f"model={model}\n"
                f"chat error: {chat_error}\n"
                f"generate error: HTTP {e.code}: {body or e.reason}"
            )
        return False, (
            f"host={host}\n"
            f"model={model}\n"
            f"generate error: HTTP {e.code}: {body or e.reason}"
        )
    except Exception as e:
        if chat_error:
            return False, (
                f"host={host}\n"
                f"model={model}\n"
                f"chat error: {chat_error}\n"
                f"generate error: {e}"
            )
        return False, (
            f"host={host}\n"
            f"model={model}\n"
            f"generate error: {e}"
        )

    return False, f"host={host}\nmodel={model}\nOllama доступна, но модель не вернула ответа."