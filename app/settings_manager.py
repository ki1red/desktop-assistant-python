from app.indexing.db import get_connection


class SettingsManager:
    def get(self, key: str, default: str | None = None) -> str | None:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row:
            return row["value"]
        return default

    def set(self, key: str, value: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO user_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()
        conn.close()