from datetime import datetime

from rapidfuzz import fuzz

from app.indexing.db import get_connection
from app.text_variants import normalize_query_text, build_name_variants


def upsert_quick_target(name: str, target_path: str, target_type: str, provider: str = "local", increment_usage: bool = True):
    if not name or not target_path or not target_type:
        return

    normalized_name = normalize_query_text(name)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, usage_count
    FROM quick_access_targets
    WHERE target_path = ?
    """, (target_path,))
    row = cur.fetchone()

    now = datetime.utcnow().isoformat()

    if row:
        if increment_usage:
            cur.execute("""
            UPDATE quick_access_targets
            SET name = ?, normalized_name = ?, target_type = ?, provider = ?,
                usage_count = usage_count + 1, last_used_at = ?
            WHERE id = ?
            """, (name, normalized_name, target_type, provider, now, row["id"]))
        else:
            cur.execute("""
            UPDATE quick_access_targets
            SET name = ?, normalized_name = ?, target_type = ?, provider = ?, last_used_at = ?
            WHERE id = ?
            """, (name, normalized_name, target_type, provider, now, row["id"]))
    else:
        cur.execute("""
        INSERT INTO quick_access_targets
        (name, normalized_name, target_path, target_type, provider, usage_count, last_used_at, is_pinned)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (name, normalized_name, target_path, target_type, provider, 1 if increment_usage else 0, now))

    conn.commit()
    conn.close()


def get_quick_access_match(query_text: str, allowed_types: list[str]):
    normalized_query = normalize_query_text(query_text or "")
    if not normalized_query:
        return None

    conn = get_connection()
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in allowed_types)
    cur.execute(f"""
    SELECT name, normalized_name, target_path, target_type, provider, usage_count, is_pinned
    FROM quick_access_targets
    WHERE target_type IN ({placeholders})
    """, allowed_types)

    rows = cur.fetchall()
    conn.close()

    best = None
    best_score = 0.0

    query_variants = build_name_variants(normalized_query)

    for row in rows:
        candidate_variants = build_name_variants(row["name"])
        score = 0.0

        for qv in query_variants:
            for cv in candidate_variants:
                score = max(
                    score,
                    fuzz.ratio(qv, cv),
                    fuzz.token_sort_ratio(qv, cv),
                    fuzz.token_set_ratio(qv, cv)
                )
                if qv == cv:
                    score = max(score, 100.0)

        score += min((row["usage_count"] or 0) * 2.0, 12.0)
        if row["is_pinned"]:
            score += 10.0

        if score > best_score:
            best_score = score
            best = {
                "name": row["name"],
                "path": row["target_path"],
                "target_type": row["target_type"],
                "provider": row["provider"],
                "score": min(score, 120.0)
            }

    return best


def pin_quick_target(target_path: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    UPDATE quick_access_targets
    SET is_pinned = 1
    WHERE target_path = ?
    """, (target_path,))
    conn.commit()
    conn.close()