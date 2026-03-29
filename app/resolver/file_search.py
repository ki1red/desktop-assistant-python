import os
from pathlib import Path
from typing import List, Optional

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate


def detect_explicit_path(text: str) -> Optional[str]:
    text = text.strip().strip('"')
    if os.path.exists(text):
        return text
    return None


def search_indexed_targets(query: str, wanted_type: str) -> List[Candidate]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT path, name, target_type, source_kind
        FROM filesystem_index
        WHERE target_type = ?
    """, (wanted_type,))

    rows = cur.fetchall()
    conn.close()

    results = []
    for row in rows:
        score = score_candidate(query, row["name"], row["source_kind"])
        if score >= 78:
            results.append(Candidate(
                name=row["name"],
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:20]