import os
from pathlib import Path
from typing import List, Optional, Set

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate
from app.config import APP_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.text_variants import normalize_basic, build_name_variants
from app.utils import get_priority_roots


PRIORITY_APP_SOURCES = {
    "cwd",
    "desktop",
    "start_menu_user",
    "start_menu_common"
}


def _fetch_app_rows_prefiltered(query: str, source_kinds: Optional[Set[str]] = None, limit: int = 300):
    conn = get_connection()
    cur = conn.cursor()

    conditions = ["target_type = 'app'"]
    params = []

    if source_kinds:
        placeholders = ",".join("?" for _ in source_kinds)
        conditions.append(f"source_kind IN ({placeholders})")
        params.extend(list(source_kinds))

    variant_conditions = []
    for variant in sorted(build_name_variants(query)):
        v = normalize_basic(variant)
        if len(v) >= 2:
            variant_conditions.append("search_blob LIKE ?")
            params.append(f"%{v}%")

    if variant_conditions:
        conditions.append("(" + " OR ".join(variant_conditions[:8]) + ")")

    sql = f"""
        SELECT path, name, target_type, source_kind, normalized_name, search_blob, parent_path
        FROM filesystem_index
        WHERE {' AND '.join(conditions)}
        LIMIT {limit}
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def _score_single_app_candidate(query: str, row) -> float:
    name = row["name"]
    path = row["path"]
    source_kind = row["source_kind"]
    parent_path = row["parent_path"] or ""

    path_lower = path.lower()
    if source_kind == "recent":
        return 0.0

    if not (
        path_lower.endswith(".exe") or
        path_lower.endswith(".lnk") or
        path_lower.endswith(".url")
    ):
        return 0.0

    query_norm = normalize_basic(query)
    name_norm = normalize_basic(name)
    path_norm = normalize_basic(path)
    parent_name = Path(parent_path).name if parent_path else ""
    parent_norm = normalize_basic(parent_name)

    base_score = score_candidate(query, name, source_kind, path)

    if parent_name:
        base_score = max(base_score, score_candidate(query, f"{parent_name} {name}", source_kind, path))

    if query_norm and query_norm in path_norm:
        base_score += 6.0

    if "start menu" in path_lower or "\\programs\\" in path_lower:
        base_score += 5.0

    # Специальная логика для Яндекс Браузера
    browser_query = (
        "браузер" in query_norm or
        "browser" in query_norm or
        "яндекс браузер" in query_norm or
        "yandex browser" in query_norm
    )

    if browser_query:
        # Сильный штраф субпродуктам
        bad_subapps = ["почта", "музыка", "диск", "mail", "music", "disk"]
        if any(marker in name_norm for marker in bad_subapps):
            base_score -= 25.0

        if any(marker in parent_norm for marker in bad_subapps):
            base_score -= 20.0

        # Буст если браузер угадывается в пути или папке
        browser_markers = ["browser", "браузер", "yandexbrowser", "yandex browser"]
        if any(marker in path_norm for marker in browser_markers):
            base_score += 20.0
        if any(marker in parent_norm for marker in browser_markers):
            base_score += 20.0
        if any(marker in name_norm for marker in browser_markers):
            base_score += 20.0

    return max(0.0, min(base_score, 100.0))


def _score_rows(query: str, rows) -> List[Candidate]:
    results = []
    for row in rows:
        score = _score_single_app_candidate(query, row)
        if score >= APP_MATCH_THRESHOLD:
            results.append(Candidate(
                name=row["name"],
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def _fallback_scan_apps(query: str) -> List[Candidate]:
    roots = get_priority_roots()
    results = []

    for source_kind in ["start_menu_user", "start_menu_common", "desktop", "cwd"]:
        root_path = roots.get(source_kind)
        if not root_path or not os.path.exists(root_path):
            continue

        try:
            for root, _, files in os.walk(root_path):
                for f in files:
                    if not f.lower().endswith((".lnk", ".url", ".exe")):
                        continue

                    full_path = str(Path(root) / f)
                    name = Path(f).stem
                    row_like = {
                        "name": name,
                        "path": full_path,
                        "source_kind": source_kind,
                        "parent_path": str(Path(full_path).parent),
                        "target_type": "app"
                    }

                    score = _score_single_app_candidate(query, row_like)
                    if score >= APP_MATCH_THRESHOLD:
                        results.append(Candidate(
                            name=name,
                            path=full_path,
                            score=score,
                            target_type="app"
                        ))
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def find_best_app_matches(query: str) -> List[Candidate]:
    priority_rows = _fetch_app_rows_prefiltered(query, PRIORITY_APP_SOURCES, limit=250)
    priority_results = _score_rows(query, priority_rows)

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    all_rows = _fetch_app_rows_prefiltered(query, PRIORITY_APP_SOURCES, limit=500)
    all_results = _score_rows(query, all_rows)

    if all_results:
        return all_results

    return _fallback_scan_apps(query)