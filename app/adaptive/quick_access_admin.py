from app.indexing.db import get_connection
from app.text_variants import normalize_query_text


class QuickAccessAdmin:
    def list_targets(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT id, name, normalized_name, target_path, target_type, provider, usage_count, last_used_at, is_pinned
        FROM quick_access_targets
        ORDER BY is_pinned DESC, usage_count DESC, name ASC
        """)
        rows = cur.fetchall()
        conn.close()
        return rows

    def upsert_target(self, name: str, target_path: str, target_type: str, provider: str, is_pinned: bool):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO quick_access_targets
        (name, normalized_name, target_path, target_type, provider, usage_count, last_used_at, is_pinned)
        VALUES (?, ?, ?, ?, ?, 0, NULL, ?)
        ON CONFLICT(target_path) DO UPDATE SET
            name = excluded.name,
            normalized_name = excluded.normalized_name,
            target_type = excluded.target_type,
            provider = excluded.provider,
            is_pinned = excluded.is_pinned
        """, (
            name,
            normalize_query_text(name),
            target_path,
            target_type,
            provider,
            1 if is_pinned else 0
        ))
        conn.commit()
        conn.close()

    def delete_target(self, target_path: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM quick_access_targets WHERE target_path = ?", (target_path,))
        conn.commit()
        conn.close()