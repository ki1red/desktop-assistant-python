import subprocess
from pathlib import Path

from app.logger import get_logger


logger = get_logger("ollama_discovery")

OLLAMA_LIST_TIMEOUT_SEC = 5


def _get_no_window_creationflags() -> int:
    """
    Чтобы на Windows не мигало консольное окно при вызове ollama list.
    """
    try:
        return subprocess.CREATE_NO_WINDOW
    except AttributeError:
        return 0


def list_ollama_models_cli(timeout_sec: int = OLLAMA_LIST_TIMEOUT_SEC) -> list[str]:
    """
    Сначала пытаемся взять обычный `ollama list`.

    Важно:
    после старта Windows Ollama может быть ещё не готова.
    Поэтому здесь ОБЯЗАТЕЛЬНО нужен timeout, иначе UI может зависнуть
    ещё до запуска фонового listener'а.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            timeout=timeout_sec,
            creationflags=_get_no_window_creationflags()
        )

        if result.returncode != 0:
            logger.warning(
                "ollama list завершился с кодом %s. stderr=%s",
                result.returncode,
                (result.stderr or "").strip()[:500]
            )
            return []

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return []

        models = []

        for line in lines[1:]:
            parts = line.split()
            if not parts:
                continue

            model_name = parts[0].strip()
            if model_name and model_name.upper() != "NAME":
                models.append(model_name)

        return sorted(set(models))

    except subprocess.TimeoutExpired:
        logger.warning("ollama list не ответил за %s сек. Пропускаю автообнаружение моделей.", timeout_sec)
        return []
    except FileNotFoundError:
        logger.warning("Команда ollama не найдена в PATH. Пропускаю автообнаружение моделей.")
        return []
    except Exception as e:
        logger.exception("Ошибка при выполнении ollama list: %s", e)
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
        for registry_dir in manifests_dir.iterdir():
            if not registry_dir.is_dir():
                continue

            for namespace_dir in registry_dir.iterdir():
                if not namespace_dir.is_dir():
                    continue

                namespace = namespace_dir.name

                for model_dir in namespace_dir.iterdir():
                    if not model_dir.is_dir():
                        continue

                    model_name = model_dir.name

                    for tag_file in model_dir.iterdir():
                        if tag_file.is_file():
                            tag = tag_file.name
                            models.append(f"{namespace}/{model_name}:{tag}")

    except Exception as e:
        logger.exception("Ошибка fallback-сканирования моделей Ollama: %s", e)
        return []

    return sorted(set(models))


def list_available_ollama_models(models_path: str) -> list[str]:
    models = list_ollama_models_cli()
    if models:
        return models

    return list_ollama_models_from_path(models_path)