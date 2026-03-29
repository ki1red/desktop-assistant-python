from typing import List, Optional, Set

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate
from app.config import APP_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.text_variants import normalize_basic, split_tokens


PRIORITY_APP_SOURCES = {
    "cwd",
    "desktop",
    "recent",
    "start_menu_user",
    "start_menu_common"
}


def _is_junk_recent_shortcut(name: str, source_kind: str) -> bool:
    if source_kind != "recent":
        return False

    n = normalize_basic(name)

    junk_markers = [
        "msteamssystem initiated",
        "system initiated",
        "initiated",
        "notification",
        "runtime broker",
        "installer",
        "setup",
        "update",
        "updater"
    ]

    if any(marker in n for marker in junk_markers):
        return True

    if len(n) <= 2:
        return True

    return False


def _fetch_app_rows_prefiltered(query: str, source_kinds: Optional[Set[str]] = None, limit: int = 300):
    conn = get_connection()
    cur = conn.cursor()

    normalized = normalize_basic(query)
    tokens = [t for t in split_tokens(normalized) if len(t) >= 2]

    conditions = ["target_type = 'app'"]
    params = []

    if source_kinds:
        placeholders = ",".join("?" for _ in source_kinds)
        conditions.append(f"source_kind IN ({placeholders})")
        params.extend(list(source_kinds))

    token_conditions = []
    for token in tokens[:4]:
        token_conditions.append("normalized_name LIKE ?")
        params.append(f"%{token}%")

    if token_conditions:
        conditions.append("(" + " OR ".join(token_conditions) + ")")

    sql = f"""
        SELECT path, name, target_type, source_kind, normalized_name
        FROM filesystem_index
        WHERE {' AND '.join(conditions)}
        LIMIT {limit}
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def _score_rows(query: str, rows) -> List[Candidate]:
    results = []
    for row in rows:
        if _is_junk_recent_shortcut(row["name"], row["source_kind"]):
            continue

        score = score_candidate(query, row["name"], row["source_kind"], row["path"])
        if score >= APP_MATCH_THRESHOLD:
            results.append(Candidate(
                name=row["name"],
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def find_best_app_matches(query: str) -> List[Candidate]:
    priority_rows = _fetch_app_rows_prefiltered(query, PRIORITY_APP_SOURCES, limit=200)
    priority_results = _score_rows(query, priority_rows)

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    all_rows = _fetch_app_rows_prefiltered(query, None, limit=400)
    return _score_rows(query, all_rows)