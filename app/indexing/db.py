import sqlite3
from app.config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS filesystem_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
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
        success INTEGER NOT NULL,
        used_at TEXT NOT NULL
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

    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_name ON filesystem_index(normalized_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_type ON filesystem_index(target_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_source ON filesystem_index(source_kind)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_history_query ON usage_history(query_text)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alias_alias ON user_aliases(alias)")

    conn.commit()
    conn.close()