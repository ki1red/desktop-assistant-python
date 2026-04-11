from urllib.parse import quote

from app.indexing.db import get_connection
from app.settings_manager import SettingsManager
from app.settings_service import settings_service


class ProviderRouter:
    def __init__(self):
        self.settings = SettingsManager()
        self._config = settings_service.get_all()
        settings_service.subscribe(self._on_settings_changed)

    def _on_settings_changed(self, config_snapshot: dict):
        self._config = config_snapshot

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
        url = self.build_url(provider_key, query_text)
        if url:
            return url
        return self.build_url("browser_google", query_text)

    def build_default_youtube_url(self, query_text: str) -> str | None:
        provider_key = self.settings.get("default_youtube_provider", "youtube_search")
        url = self.build_url(provider_key, query_text)
        if url:
            return url
        return self.build_url("youtube_search", query_text)

    def build_default_music_url(self, query_text: str) -> str | None:
        provider_key = self.settings.get("default_music_provider", "yandex_music")
        url = self.build_url(provider_key, query_text)
        if url:
            return url

        for fallback_key in ["yandex_music", "spotify", "youtube_music", "vk_music"]:
            url = self.build_url(fallback_key, query_text)
            if url:
                return url

        return None