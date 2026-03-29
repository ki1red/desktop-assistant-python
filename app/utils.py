import os
from pathlib import Path

from app.config import PRIORITY_ROOTS_CONFIG


def safe_name_from_path(path: str) -> str:
    return Path(path).stem.lower()


def get_windows_drives():
    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(drive)
    return drives


def get_priority_roots() -> dict:
    user_profile = os.path.expandvars(r"%USERPROFILE%")
    appdata = os.path.expandvars(r"%AppData%")
    programdata = os.path.expandvars(r"%ProgramData%")

    roots = {
        "cwd": os.getcwd(),
        "desktop": os.path.join(user_profile, "Desktop"),
        "documents": os.path.join(user_profile, "Documents"),
        "downloads": os.path.join(user_profile, "Downloads"),
        "recent": os.path.join(appdata, r"Microsoft\Windows\Recent"),
        "start_menu_user": os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs"),
        "start_menu_common": os.path.join(programdata, r"Microsoft\Windows\Start Menu\Programs"),
    }

    enabled_roots = {}
    for key, value in roots.items():
        if PRIORITY_ROOTS_CONFIG.get(key, False):
            enabled_roots[key] = value

    for i, path in enumerate(PRIORITY_ROOTS_CONFIG.get("extra_paths", []), start=1):
        enabled_roots[f"extra_{i}"] = path

    return enabled_roots