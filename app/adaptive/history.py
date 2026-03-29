from datetime import datetime

from rapidfuzz import fuzz

from app.indexing.db import get_connection
from app.text_variants import normalize_basic, build_name_variants


def init_history_tables():
    # Уже создаются в init_db()
    pass


def save_usage(query_text: str, intent: str, target_name: str, target_path: str, target_type: str, success: bool):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO usage_history (query_text, intent, target_name, target_path, target_type, success, used_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        query_text,
        intent,
        target_name,
        target_path,
        target_type,
        1 if success else 0,
        datetime.utcnow().isoformat()
    ))

    normalized_query = normalize_basic(query_text or "")
    if normalized_query and target_path:
        cur.execute("""
        SELECT id, open_count, fail_count
        FROM usage_stats
        WHERE normalized_query = ? AND intent = ? AND target_path = ?
        """, (normalized_query, intent, target_path))
        row = cur.fetchone()

        if row:
            if success:
                cur.execute("""
                UPDATE usage_stats
                SET open_count = open_count + 1,
                    last_used_at = ?,
                    target_name = ?,
                    target_type = ?
                WHERE id = ?
                """, (datetime.utcnow().isoformat(), target_name, target_type, row["id"]))
            else:
                cur.execute("""
                UPDATE usage_stats
                SET fail_count = fail_count + 1,
                    last_used_at = ?
                WHERE id = ?
                """, (datetime.utcnow().isoformat(), row["id"]))
        else:
            cur.execute("""
            INSERT INTO usage_stats
            (normalized_query, intent, target_name, target_path, target_type, open_count, fail_count, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                normalized_query,
                intent,
                target_name,
                target_path,
                target_type,
                1 if success else 0,
                0 if success else 1,
                datetime.utcnow().isoformat()
            ))

    conn.commit()
    conn.close()


def get_usage_bonus(query_text: str, target_path: str) -> float:
    normalized_query = normalize_basic(query_text or "")
    if not normalized_query or not target_path:
        return 0.0

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT open_count, fail_count
    FROM usage_stats
    WHERE normalized_query = ? AND target_path = ?
    """, (normalized_query, target_path))

    row = cur.fetchone()
    conn.close()

    if not row:
        return 0.0

    open_count = row["open_count"] or 0
    fail_count = row["fail_count"] or 0

    bonus = open_count * 2.0 - fail_count * 3.0
    return max(0.0, min(bonus, 12.0))


def _simple_similarity(query_text: str, candidate_name: str) -> float:
    q_variants = build_name_variants(query_text or "")
    c_variants = build_name_variants(candidate_name or "")

    best = 0.0
    for qv in q_variants:
        for cv in c_variants:
            score = max(
                fuzz.ratio(qv, cv),
                fuzz.token_sort_ratio(qv, cv),
                fuzz.token_set_ratio(qv, cv)
            )
            if qv == cv:
                score = max(score, 100)
            if score > best:
                best = score

    return best


def get_direct_usage_match(query_text: str, allowed_types: list[str], intent: str | None = None):
    normalized_query = normalize_basic(query_text or "")
    if not normalized_query:
        return None

    conn = get_connection()
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in allowed_types)
    sql = f"""
    SELECT target_name, target_path, target_type, open_count, fail_count, intent
    FROM usage_stats
    WHERE target_type IN ({placeholders})
    """
    params = list(allowed_types)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    best = None
    best_score = 0.0

    for row in rows:
        if row["fail_count"] and row["fail_count"] > row["open_count"]:
            continue

        score = _simple_similarity(normalized_query, row["target_name"])
        score += min((row["open_count"] or 0) * 2.5, 15.0)

        if intent and row["intent"] == intent:
            score += 3.0

        if score > best_score:
            best_score = score
            best = {
                "name": row["target_name"],
                "path": row["target_path"],
                "target_type": row["target_type"],
                "score": min(score, 100.0)
            }

    return best


def register_negative_feedback(target_path: str):
    if not target_path:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    UPDATE usage_stats
    SET fail_count = fail_count + 1
    WHERE target_path = ?
    """, (target_path,))

    conn.commit()
    conn.close()