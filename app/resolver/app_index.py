from typing import List, Optional, Set

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate
from app.config import APP_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.text_variants import normalize_basic


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

    # Слишком техничные recent-ярлыки с кучей мусора и цифр
    digit_count = sum(ch.isdigit() for ch in n)
    if digit_count >= 3 and len(n.split()) <= 3:
        return True

    return False


def _fetch_app_rows(source_kinds: Optional[Set[str]] = None):
    conn = get_connection()
    cur = conn.cursor()

    if source_kinds:
        placeholders = ",".join("?" for _ in source_kinds)
        query = f"""
            SELECT path, name, target_type, source_kind
            FROM filesystem_index
            WHERE target_type = 'app'
              AND source_kind IN ({placeholders})
        """
        cur.execute(query, list(source_kinds))
    else:
        cur.execute("""
            SELECT path, name, target_type, source_kind
            FROM filesystem_index
            WHERE target_type = 'app'
        """)

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
    priority_rows = _fetch_app_rows(PRIORITY_APP_SOURCES)
    priority_results = _score_rows(query, priority_rows)

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    all_rows = _fetch_app_rows(None)
    return _score_rows(query, all_rows)