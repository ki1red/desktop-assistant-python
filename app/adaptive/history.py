from datetime import datetime

from app.indexing.db import get_connection


def init_history_tables():
    # Таблицы уже создаются в init_db().
    # Оставляем функцию как совместимый entrypoint на будущее.
    pass


def save_usage(query_text: str, intent: str, target_name: str, target_path: str, success: bool):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO usage_history (query_text, intent, target_name, target_path, success, used_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        query_text,
        intent,
        target_name,
        target_path,
        1 if success else 0,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()


def get_usage_bonus(query_text: str, target_path: str) -> float:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT COUNT(*) as cnt
    FROM usage_history
    WHERE query_text = ? AND target_path = ? AND success = 1
    """, (query_text, target_path))

    row = cur.fetchone()
    conn.close()

    count = row["cnt"] if row else 0
    return min(count * 2.0, 12.0)