from urllib.parse import quote

from app.indexing.db import get_connection
from app.settings_manager import SettingsManager


class ProviderRouter:
    def __init__(self):
        self.settings = SettingsManager()

    def get_provider_route(self, provider_key: str):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT provider_key, provider_type, title, url_template, is_enabled
        FROM provider_routes
        WHERE provider_key = ?
        """, (provider_key,))
        row = cur.fetchone()
        conn.close()
        return row

    def build_url(self, provider_key: str, query_text: str) -> str | None:
        route = self.get_provider_route(provider_key)
        if not route or not route["is_enabled"]:
            return None

        encoded = quote(query_text)
        return route["url_template"].replace("{query}", encoded)

    def build_default_web_search_url(self, query_text: str) -> str | None:
        provider_key = self.settings.get("default_web_search_provider", "browser_google")
        return self.build_url(provider_key, query_text)

    def build_default_youtube_url(self, query_text: str) -> str | None:
        provider_key = self.settings.get("default_youtube_provider", "youtube_search")
        return self.build_url(provider_key, query_text)

    def build_default_music_url(self, query_text: str) -> str | None:
        provider_key = self.settings.get("default_music_provider", "yandex_music")
        return self.build_url(provider_key, query_text)