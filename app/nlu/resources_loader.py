import json
from pathlib import Path

from app.app_paths import BUNDLE_ROOT

_NLU_DIR = BUNDLE_ROOT / "config" / "nlu"


def _load_lines(filename: str) -> list[str]:
    path = _NLU_DIR / filename
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _load_json(filename: str) -> dict:
    path = _NLU_DIR / filename
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class NLUResources:
    def __init__(self):
        self.reload()

    def reload(self):
        self.polite_words = _load_lines("polite_words.txt")
        self.filler_words = _load_lines("filler_words.txt")
        self.command_verbs = _load_lines("command_verbs.txt")
        self.dictation_replacements = _load_json("dictation_replacements.json")
        self.extension_aliases = _load_json("extension_aliases.json")


nlu_resources = NLUResources()