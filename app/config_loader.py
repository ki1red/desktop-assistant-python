import copy
import json
import os
from pathlib import Path

from app.app_paths import (
    USER_CONFIG_PATH,
    DEFAULT_CONFIG_PATH,
    DB_PATH,
    DATA_DIR,
    TEMP_DIR,
    LOGS_DIR,
    ensure_app_dirs,
)


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_existing_paths() -> list[str]:
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    programdata = Path(os.environ.get("ProgramData", "C:/ProgramData"))

    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents",
        home / "OneDrive" / "Downloads",
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        programdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
    ]

    result = []
    for p in candidates:
        if p.exists():
            result.append(str(p))
    return sorted(set(result))


def _normalize_runtime_paths(cfg: dict) -> dict:
    cfg.setdefault("paths", {})
    cfg["paths"]["temp_dir"] = str(TEMP_DIR)
    cfg["paths"]["data_dir"] = str(DATA_DIR)
    cfg["paths"]["database_path"] = str(DB_PATH)
    cfg["paths"]["logs_dir"] = str(LOGS_DIR)

    cfg.setdefault("priority_roots", {})
    extra_paths = cfg["priority_roots"].get("extra_paths", [])
    if not extra_paths:
        cfg["priority_roots"]["extra_paths"] = _resolve_existing_paths()

    return cfg


class ConfigLoader:
    def __init__(self, path: Path = USER_CONFIG_PATH):
        self.path = path
        ensure_app_dirs()
        self.data = self._load()

    def _load_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load(self) -> dict:
        defaults = self._load_json(DEFAULT_CONFIG_PATH)

        if self.path.exists():
            user_cfg = self._load_json(self.path)
        else:
            user_cfg = {}

        merged = _deep_merge(defaults, user_cfg)
        merged = _normalize_runtime_paths(merged)
        return merged

    def get(self) -> dict:
        return self.data

    def save(self, data: dict):
        data = _normalize_runtime_paths(data)
        ensure_app_dirs()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.data = data