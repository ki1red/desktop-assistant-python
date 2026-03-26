import os
from pathlib import Path


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

    return {
        "cwd": os.getcwd(),
        "desktop": os.path.join(user_profile, "Desktop"),
        "documents": os.path.join(user_profile, "Documents"),
        "downloads": os.path.join(user_profile, "Downloads"),
        "recent": os.path.join(appdata, r"Microsoft\Windows\Recent"),
        "start_menu_user": os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs"),
        "start_menu_common": os.path.join(programdata, r"Microsoft\Windows\Start Menu\Programs"),
    }