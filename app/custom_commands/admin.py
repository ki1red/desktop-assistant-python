from app.indexing.db import get_connection


class CustomCommandsAdmin:
    def list_commands(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT id, phrase, command_type, payload, is_enabled
        FROM custom_commands
        ORDER BY phrase ASC
        """)
        rows = cur.fetchall()
        conn.close()
        return rows

    def upsert_command(self, phrase: str, command_type: str, payload: str, is_enabled: bool):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO custom_commands (phrase, command_type, payload, is_enabled)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(phrase) DO UPDATE SET
            command_type = excluded.command_type,
            payload = excluded.payload,
            is_enabled = excluded.is_enabled
        """, (phrase.strip(), command_type.strip(), payload.strip(), 1 if is_enabled else 0))
        conn.commit()
        conn.close()

    def delete_command(self, phrase: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM custom_commands WHERE phrase = ?", (phrase.strip(),))
        conn.commit()
        conn.close()

    def resolve_command(self, phrase: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT phrase, command_type, payload, is_enabled
        FROM custom_commands
        WHERE phrase = ?
        """, (phrase.strip(),))
        row = cur.fetchone()
        conn.close()
        return row