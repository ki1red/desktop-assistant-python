import os


def validate_path_step_by_step(path_text: str) -> tuple[bool, str]:
    """
    Проверяет путь по сегментам и сообщает, где именно он ломается.
    """
    raw = path_text.strip().strip('"')
    if not raw:
        return False, "Пустой путь."

    normalized = os.path.normpath(raw)

    drive, tail = os.path.splitdrive(normalized)
    if drive and not os.path.exists(drive + "\\"):
        return False, f"Диск не существует: {drive}\\"

    current = drive + "\\" if drive else ""
    parts = [p for p in tail.strip("\\/").split("\\") if p]

    for part in parts:
        current = os.path.join(current, part) if current else part
        if not os.path.exists(current):
            return False, f"Не найден сегмент пути: {current}"

    return True, normalized


def looks_like_explicit_path(text: str) -> bool:
    text = text.strip().strip('"')
    return (
        ":\\" in text or
        text.startswith("\\\\") or
        "/" in text or
        "\\" in text
    )