import os
from pathlib import Path

from app.config import INDEX_BATCH_SIZE
from app.indexing.db import get_connection, init_db
from app.text_variants import normalize_basic
from app.utils import get_priority_roots, get_windows_drives


SKIP_DIRS = {
    "windows",
    "program files",
    "program files (x86)",
    "$recycle.bin",
    "system volume information"
}


def _classify_entry(path: str) -> str:
    lower = path.lower()
    if lower.endswith((".lnk", ".url", ".exe")):
        return "app"
    if os.path.isdir(path):
        return "folder"
    return "file"


def _make_record(path: str, source_kind: str):
    p = Path(path)
    name = p.stem if p.suffix else p.name
    target_type = _classify_entry(path)
    extension = p.suffix.lower().replace(".", "") if p.suffix else ""
    normalized_name = normalize_basic(p.name)

    return (
        str(p),
        name,
        normalized_name,
        target_type,
        source_kind,
        str(p.parent),
        extension
    )


def rebuild_index():
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM filesystem_index")
    conn.commit()

    buffer = []

    roots = get_priority_roots()

    ordered_sources = [
        "cwd",
        "desktop",
        "documents",
        "downloads",
        "recent",
        "start_menu_user",
        "start_menu_common",
    ]

    for source_kind in ordered_sources:
        root_path = roots.get(source_kind)
        if not root_path or not os.path.exists(root_path):
            continue

        for root, dirs, files in os.walk(root_path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]

            try:
                for d in dirs:
                    full_path = str(Path(root) / d)
                    buffer.append(_make_record(full_path, source_kind))

                for f in files:
                    full_path = str(Path(root) / f)
                    buffer.append(_make_record(full_path, source_kind))

                if len(buffer) >= INDEX_BATCH_SIZE:
                    cur.executemany("""
                        INSERT OR REPLACE INTO filesystem_index
                        (path, name, normalized_name, target_type, source_kind, parent_path, extension)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, buffer)
                    conn.commit()
                    buffer.clear()

            except (PermissionError, OSError):
                continue

    for drive in get_windows_drives():
        for root, dirs, files in os.walk(drive, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]

            try:
                for d in dirs:
                    full_path = str(Path(root) / d)
                    buffer.append(_make_record(full_path, "global"))

                for f in files:
                    full_path = str(Path(root) / f)
                    buffer.append(_make_record(full_path, "global"))

                if len(buffer) >= INDEX_BATCH_SIZE:
                    cur.executemany("""
                        INSERT OR REPLACE INTO filesystem_index
                        (path, name, normalized_name, target_type, source_kind, parent_path, extension)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, buffer)
                    conn.commit()
                    buffer.clear()

            except (PermissionError, OSError):
                continue

    if buffer:
        cur.executemany("""
            INSERT OR REPLACE INTO filesystem_index
            (path, name, normalized_name, target_type, source_kind, parent_path, extension)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, buffer)
        conn.commit()

    conn.close()


def get_index_count() -> int:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM filesystem_index")
    count = cur.fetchone()[0]
    conn.close()
    return count