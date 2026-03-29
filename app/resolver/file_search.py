import os
from typing import List, Optional

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate
from app.config import FILE_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.utils import get_priority_roots


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


def _fetch_candidates_by_type(wanted_type: str, source_kinds: Optional[set[str]] = None):
    conn = get_connection()
    cur = conn.cursor()

    if source_kinds:
        placeholders = ",".join("?" for _ in source_kinds)
        query = f"""
            SELECT path, name, target_type, source_kind
            FROM filesystem_index
            WHERE target_type = ?
              AND source_kind IN ({placeholders})
        """
        params = [wanted_type, *source_kinds]
        cur.execute(query, params)
    else:
        cur.execute("""
            SELECT path, name, target_type, source_kind
            FROM filesystem_index
            WHERE target_type = ?
        """, (wanted_type,))

    rows = cur.fetchall()
    conn.close()
    return rows


def _score_rows(query: str, rows) -> List[Candidate]:
    results = []

    for row in rows:
        score = score_candidate(query, row["name"], row["source_kind"], row["path"])
        if score >= FILE_MATCH_THRESHOLD:
            results.append(Candidate(
                name=row["name"],
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def search_indexed_targets(query: str, wanted_type: str) -> List[Candidate]:
    priority_source_kinds = _build_priority_source_kinds()

    priority_rows = _fetch_candidates_by_type(wanted_type, priority_source_kinds)
    priority_results = _score_rows(query, priority_rows)

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    all_rows = _fetch_candidates_by_type(wanted_type, None)
    return _score_rows(query, all_rows)