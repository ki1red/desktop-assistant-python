import sqlite3
from app.config import DB_PATH


def get_connection(enable_cancel_progress: bool = False):
    """
    Возвращает соединение с SQLite.

    ВАЖНО:
    enable_cancel_progress=False по умолчанию.
    Нельзя глобально вешать runtime_control на все SQLite-запросы,
    иначе отмена голосовой команды может прервать индексацию,
    запись истории, настройки и другие фоновые операции.

    enable_cancel_progress=True нужно использовать только в тех местах,
    где долгий поиск действительно должен отменяться пользователем.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA busy_timeout = 30000")
    except Exception:
        pass

    if enable_cancel_progress:
        try:
            from app.runtime_control import runtime_control

            def _progress_handler():
                return 1 if runtime_control.is_cancelled() else 0

            conn.set_progress_handler(_progress_handler, 2000)
        except Exception:
            pass

    return conn


def _get_table_columns(cur, table_name: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(cur, table_name: str, column_name: str, column_sql: str):
    columns = _get_table_columns(cur, table_name)
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def _ensure_index_metadata_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS index_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)


def get_index_metadata(key: str, default: str = "") -> str:
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_index_metadata_table(cur)
        cur.execute("SELECT value FROM index_metadata WHERE key = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return default
        return str(row["value"])
    except Exception:
        return default


def set_index_metadata(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    _ensure_index_metadata_table(cur)
    cur.execute("""
    INSERT INTO index_metadata (key, value)
    VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()


def set_index_metadata_many(values: dict):
    conn = get_connection()
    cur = conn.cursor()
    _ensure_index_metadata_table(cur)

    rows = [(str(k), str(v)) for k, v in values.items()]
    cur.executemany("""
    INSERT INTO index_metadata (key, value)
    VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, rows)

    conn.commit()
    conn.close()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS filesystem_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        search_blob TEXT,
        target_type TEXT NOT NULL,
        source_kind TEXT NOT NULL,
        parent_path TEXT,
        extension TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usage_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_text TEXT NOT NULL,
        intent TEXT,
        target_name TEXT,
        target_path TEXT,
        target_type TEXT,
        success INTEGER NOT NULL,
        used_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usage_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        normalized_query TEXT NOT NULL,
        intent TEXT,
        target_name TEXT,
        target_path TEXT NOT NULL,
        target_type TEXT,
        open_count INTEGER NOT NULL DEFAULT 0,
        fail_count INTEGER NOT NULL DEFAULT 0,
        last_used_at TEXT,
        UNIQUE(normalized_query, intent, target_path)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quick_access_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        target_path TEXT NOT NULL UNIQUE,
        target_type TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'local',
        usage_count INTEGER NOT NULL DEFAULT 0,
        last_used_at TEXT,
        is_pinned INTEGER NOT NULL DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS provider_routes (
        provider_key TEXT PRIMARY KEY,
        provider_type TEXT NOT NULL,
        title TEXT NOT NULL,
        url_template TEXT NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS custom_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phrase TEXT NOT NULL UNIQUE,
        command_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alias TEXT NOT NULL UNIQUE,
        target_path TEXT NOT NULL,
        target_type TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    _ensure_index_metadata_table(cur)

    _add_column_if_missing(cur, "filesystem_index", "search_blob", "search_blob TEXT")
    _add_column_if_missing(cur, "usage_history", "target_type", "target_type TEXT")
    _add_column_if_missing(cur, "usage_stats", "target_type", "target_type TEXT")
    _add_column_if_missing(cur, "usage_stats", "fail_count", "fail_count INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(cur, "usage_stats", "last_used_at", "last_used_at TEXT")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_name ON filesystem_index(normalized_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_type ON filesystem_index(target_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_source ON filesystem_index(source_kind)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_history_query ON usage_history(query_text)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_usage_stats_query ON usage_stats(normalized_query)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quick_name ON quick_access_targets(normalized_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quick_type ON quick_access_targets(target_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_custom_phrase ON custom_commands(phrase)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alias_alias ON user_aliases(alias)")

    default_routes = [
        ("browser_google", "web_search", "Google Search", "https://www.google.com/search?q={query}", 1),
        ("youtube_search", "youtube_search", "YouTube Search", "https://www.youtube.com/results?search_query={query}", 1),
        ("yandex_music", "music_search", "Yandex Music", "https://music.yandex.ru/search?text={query}", 1),
        ("spotify", "music_search", "Spotify", "https://open.spotify.com/search/{query}", 1),
        ("youtube_music", "music_search", "YouTube Music", "https://music.youtube.com/search?q={query}", 1),
        ("vk_music", "music_search", "VK Music", "https://vk.com/audio?q={query}", 1),
    ]
    cur.executemany("""
    INSERT OR IGNORE INTO provider_routes (provider_key, provider_type, title, url_template, is_enabled)
    VALUES (?, ?, ?, ?, ?)
    """, default_routes)

    default_settings = [
        ("default_music_provider", "yandex_music"),
        ("default_web_search_provider", "browser_google"),
        ("default_youtube_provider", "youtube_search")
    ]
    cur.executemany("""
    INSERT OR IGNORE INTO user_settings (key, value)
    VALUES (?, ?)
    """, default_settings)

    conn.commit()
    conn.close()