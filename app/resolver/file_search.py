import os
from pathlib import Path
from typing import List, Optional

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate
from app.config import FILE_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.utils import get_priority_roots
from app.text_variants import build_name_variants, normalize_basic
from app.search_filters import is_bad_generic_file_candidate, is_safe_user_openable_file


def _build_priority_source_kinds() -> set[str]:
    keys = set(get_priority_roots().keys())
    keys.discard("start_menu_user")
    keys.discard("start_menu_common")
    return keys


def detect_explicit_path(text: str) -> Optional[str]:
    text = text.strip().strip('"')
    if os.path.exists(text):
        return text
    return None


def _fetch_candidates_by_type_prefiltered(
    wanted_type: str,
    query: str,
    source_kinds: Optional[set[str]] = None,
    limit: int = 400
):
    conn = get_connection()
    cur = conn.cursor()

    conditions = ["target_type = ?"]
    params = [wanted_type]

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
        SELECT path, name, target_type, source_kind, extension, normalized_name, search_blob
        FROM filesystem_index
        WHERE {' AND '.join(conditions)}
        LIMIT {limit}
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def _score_rows(query: str, rows, generic_mode: bool = False) -> List[Candidate]:
    results = []

    for row in rows:
        name = row["name"]

        if generic_mode and row["target_type"] == "file":
            if is_bad_generic_file_candidate(name):
                continue
            if not is_safe_user_openable_file(name):
                continue

        score = score_candidate(query, name, row["source_kind"], row["path"])
        if score >= FILE_MATCH_THRESHOLD:
            results.append(Candidate(
                name=name,
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def _fallback_scan_priority_roots(query: str, wanted_type: str, generic_mode: bool = False) -> List[Candidate]:
    roots = get_priority_roots()
    results = []

    for source_kind, root_path in roots.items():
        if not root_path or not os.path.exists(root_path):
            continue

        try:
            for root, dirs, files in os.walk(root_path):
                if wanted_type == "folder":
                    for d in dirs:
                        full_path = str(Path(root) / d)
                        score = score_candidate(query, d, source_kind, full_path)
                        if score >= FILE_MATCH_THRESHOLD:
                            results.append(Candidate(
                                name=d,
                                path=full_path,
                                score=score,
                                target_type="folder"
                            ))
                elif wanted_type == "file":
                    for f in files:
                        if generic_mode:
                            if is_bad_generic_file_candidate(f):
                                continue
                            if not is_safe_user_openable_file(f):
                                continue

                        full_path = str(Path(root) / f)
                        score = score_candidate(query, f, source_kind, full_path)
                        if score >= FILE_MATCH_THRESHOLD:
                            results.append(Candidate(
                                name=f,
                                path=full_path,
                                score=score,
                                target_type="file"
                            ))
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def search_indexed_targets(query: str, wanted_type: str, generic_mode: bool = False) -> List[Candidate]:
    priority_source_kinds = _build_priority_source_kinds()

    priority_rows = _fetch_candidates_by_type_prefiltered(
        wanted_type=wanted_type,
        query=query,
        source_kinds=priority_source_kinds,
        limit=250
    )
    priority_results = _score_rows(query, priority_rows, generic_mode=generic_mode)

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    all_rows = _fetch_candidates_by_type_prefiltered(
        wanted_type=wanted_type,
        query=query,
        source_kinds=None,
        limit=500
    )
    all_results = _score_rows(query, all_rows, generic_mode=generic_mode)

    if all_results:
        return all_results

    # Если индекс ничего не дал — fallback по приоритетным папкам
    return _fallback_scan_priority_roots(query, wanted_type, generic_mode=generic_mode)