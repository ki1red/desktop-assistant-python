import subprocess
from pathlib import Path


def list_ollama_models_cli() -> list[str]:
    """
    Сначала пытаемся взять обычный `ollama list`.
    Это самый надёжный способ узнать точные имена моделей.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False
        )

        if result.returncode != 0:
            return []

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return []

        models = []

        # Обычно первая строка — заголовок NAME ID SIZE MODIFIED
        for line in lines[1:]:
            parts = line.split()
            if not parts:
                continue

            model_name = parts[0].strip()
            if model_name and model_name.upper() != "NAME":
                models.append(model_name)

        return sorted(set(models))
    except Exception:
        return []


def list_ollama_models_from_path(models_path: str) -> list[str]:
    """
    Fallback-сканирование manifests.
    Поддерживает структуру:
      manifests/registry.ollama.ai/<namespace>/<model>/<tag>
    """
    if not models_path:
        return []

    base = Path(models_path)
    manifests_dir = base / "manifests"

    if not manifests_dir.exists():
        return []

    models = []

    try:
        # ищем registry-уровень
        for registry_dir in manifests_dir.iterdir():
            if not registry_dir.is_dir():
                continue

            # дальше namespace, например huihui_ai
            for namespace_dir in registry_dir.iterdir():
                if not namespace_dir.is_dir():
                    continue

                namespace = namespace_dir.name

                # дальше имя модели
                for model_dir in namespace_dir.iterdir():
                    if not model_dir.is_dir():
                        continue

                    model_name = model_dir.name

                    # внутри — файлы тегов, например 35b
                    for tag_file in model_dir.iterdir():
                        if tag_file.is_file():
                            tag = tag_file.name
                            models.append(f"{namespace}/{model_name}:{tag}")
    except Exception:
        return []

    return sorted(set(models))


def list_available_ollama_models(models_path: str) -> list[str]:
    models = list_ollama_models_cli()
    if models:
        return models

    return list_ollama_models_from_path(models_path)