from app.indexing.db import get_connection


class ProviderAdmin:
    def list_routes(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT provider_key, provider_type, title, url_template, is_enabled
        FROM provider_routes
        ORDER BY provider_type, title
        """)
        rows = cur.fetchall()
        conn.close()
        return rows

    def upsert_route(self, provider_key: str, provider_type: str, title: str, url_template: str, is_enabled: bool):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO provider_routes (provider_key, provider_type, title, url_template, is_enabled)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(provider_key) DO UPDATE SET
            provider_type = excluded.provider_type,
            title = excluded.title,
            url_template = excluded.url_template,
            is_enabled = excluded.is_enabled
        """, (provider_key, provider_type, title, url_template, 1 if is_enabled else 0))
        conn.commit()
        conn.close()

    def delete_route(self, provider_key: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM provider_routes WHERE provider_key = ?", (provider_key,))
        conn.commit()
        conn.close()