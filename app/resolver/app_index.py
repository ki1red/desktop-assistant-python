from typing import List

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate


def find_best_app_matches(query: str, threshold: int = 78) -> List[Candidate]:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT path, name, target_type, source_kind
        FROM filesystem_index
        WHERE target_type = 'app'
    """)

    rows = cur.fetchall()
    conn.close()

    results = []
    for row in rows:
        score = score_candidate(query, row["name"], row["source_kind"])
        if score >= threshold:
            results.append(Candidate(
                name=row["name"],
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:10]