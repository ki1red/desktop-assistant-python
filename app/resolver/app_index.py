import os
from pathlib import Path
from typing import List

from app.models import Candidate
from app.scoring import score_candidate
from app.utils import get_priority_roots


def _scan_shortcuts(base_path: str) -> List[Candidate]:
    results = []

    if not os.path.exists(base_path):
        return results

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith((".lnk", ".url", ".exe")):
                full_path = str(Path(root) / file)
                results.append(Candidate(
                    name=Path(file).stem,
                    path=full_path,
                    score=0,
                    target_type="app"
                ))
    return results


def collect_apps() -> List[tuple[Candidate, str]]:
    roots = get_priority_roots()
    items: List[tuple[Candidate, str]] = []

    for source_kind in ["cwd", "desktop", "recent", "start_menu_user", "start_menu_common"]:
        path = roots.get(source_kind)
        if not path:
            continue

        for item in _scan_shortcuts(path):
            items.append((item, source_kind))

    return items


def find_best_app_matches(query: str, threshold: int = 78) -> List[Candidate]:
    results = []

    for candidate, source_kind in collect_apps():
        score = score_candidate(query, candidate.name, source_kind)
        if score >= threshold:
            candidate.score = score
            results.append(candidate)

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:10]