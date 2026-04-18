import json
import urllib.request
import urllib.error


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url=url, method="GET")
    with _OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)


def _post_json(host: str, endpoint: str, payload: dict, timeout: int = 60) -> dict:
    url = f"{host.rstrip('/')}{endpoint}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with _OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)


def quick_server_check(host: str) -> tuple[bool, str]:
    host = (host or "").strip()
    if not host:
        return False, "Не указан Ollama host."

    try:
        version = _get_json(f"{host.rstrip('/')}/api/version", timeout=10)
    except Exception as e:
        return False, f"Не удалось получить /api/version\nhost={host}\nОшибка: {e}"

    try:
        tags = _get_json(f"{host.rstrip('/')}/api/tags", timeout=15)
        models = tags.get("models", [])
        model_count = len(models)
    except Exception as e:
        return False, f"Ollama отвечает по /api/version, но не удалось получить /api/tags\nhost={host}\nОшибка: {e}"

    return True, f"Ollama доступна.\nhost={host}\nversion={version.get('version', 'unknown')}\nmodels={model_count}"


def check_ollama_model(host: str, model: str) -> tuple[bool, str]:
    host = (host or "").strip()
    model = (model or "").strip()

    if not host:
        return False, "Не указан Ollama host."
    if not model:
        return False, "Не выбрана модель Ollama."

    try:
        response = _post_json(
            host,
            "/api/generate",
            {
                "model": model,
                "prompt": "Ответь одним словом: привет",
                "stream": False,
            },
            timeout=120,
        )
        content = (response.get("response") or "").strip()
        if content:
            return True, f"Модель отвечает.\nhost={host}\nmodel={model}\nresponse={content[:120]}"
        return False, f"Модель доступна, но не вернула текста.\nhost={host}\nmodel={model}"
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        return False, f"HTTP {e.code}\nhost={host}\nmodel={model}\n{body or e.reason}"
    except Exception as e:
        return False, f"Ошибка проверки модели.\nhost={host}\nmodel={model}\n{e}"