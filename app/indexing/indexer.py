import os
import time
from datetime import datetime
from pathlib import Path

from app.config import INDEX_BATCH_SIZE
from app.indexing.db import (
    get_connection,
    init_db,
    set_index_metadata_many,
)
from app.indexing.index_state import index_state
from app.text_variants import normalize_basic, build_search_blob
from app.utils import get_priority_roots, get_windows_drives
from app.logger import get_logger


logger = get_logger("indexer")


SKIP_DIRS = {
    "windows",
    "program files",
    "program files (x86)",
    "$recycle.bin",
    "system volume information",
}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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

    parent_hint = p.parent.name if p.parent else ""
    search_blob = build_search_blob(p.name, parent_hint)

    return (
        str(p),
        name,
        normalized_name,
        search_blob,
        target_type,
        source_kind,
        str(p.parent),
        extension,
    )


def _set_metadata_cursor(cur, values: dict):
    rows = [(str(k), str(v)) for k, v in values.items()]
    cur.executemany("""
    INSERT INTO index_metadata (key, value)
    VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, rows)


def _create_new_index_table(cur):
    cur.execute("DROP TABLE IF EXISTS filesystem_index_new")

    cur.execute("""
    CREATE TABLE filesystem_index_new (
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


def _create_filesystem_indexes(cur):
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_name ON filesystem_index(normalized_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_type ON filesystem_index(target_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fs_source ON filesystem_index(source_kind)")


def _insert_buffer(cur, conn, buffer: list, total_inserted: int) -> int:
    if not buffer:
        return total_inserted

    batch_size = len(buffer)

    cur.executemany("""
        INSERT OR REPLACE INTO filesystem_index_new
        (path, name, normalized_name, search_blob, target_type, source_kind, parent_path, extension)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, buffer)

    total_inserted += batch_size

    _set_metadata_cursor(cur, {
        "index_status": "building",
        "indexed_count": total_inserted,
        "last_progress_at": _now_iso(),
    })

    conn.commit()

    index_state.update(
        message=f"Индексация файлов... Обработано объектов: {total_inserted}",
        indexed_count=total_inserted,
    )

    logger.info("Индексация | batch записан во временную таблицу | batch=%s total=%s", batch_size, total_inserted)

    buffer.clear()
    return total_inserted


def _walk_source(root_path: str, source_kind: str, cur, conn, buffer: list, total_inserted: int) -> int:
    root_path = str(root_path)
    root_started = time.monotonic()
    root_seen = 0
    root_errors = 0

    logger.info("Индексация | обход корня начат | source=%s root=%s", source_kind, root_path)

    def on_walk_error(error):
        nonlocal root_errors
        root_errors += 1
        logger.warning("Индексация | ошибка обхода | root=%s error=%s", root_path, error)

    for root, dirs, files in os.walk(root_path, topdown=True, onerror=on_walk_error):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]

        try:
            for d in dirs:
                buffer.append(_make_record(str(Path(root) / d), source_kind))
                root_seen += 1

            for f in files:
                buffer.append(_make_record(str(Path(root) / f), source_kind))
                root_seen += 1

            if len(buffer) >= INDEX_BATCH_SIZE:
                total_inserted = _insert_buffer(cur, conn, buffer, total_inserted)

        except (PermissionError, OSError) as e:
            root_errors += 1
            logger.debug("Индексация | пропуск каталога | root=%s error=%s", root, e)
            continue

        except Exception as e:
            root_errors += 1
            logger.exception("Индексация | неожиданная ошибка в каталоге | root=%s error=%s", root, e)
            continue

    elapsed = time.monotonic() - root_started

    logger.info(
        "Индексация | обход корня завершён | source=%s root=%s seen=%s errors=%s elapsed=%.2fs",
        source_kind,
        root_path,
        root_seen,
        root_errors,
        elapsed,
    )

    return total_inserted


def rebuild_index():
    started = time.monotonic()
    started_at = _now_iso()

    logger.info("Индексация | rebuild_index started")
    index_state.start("Выполняется индексация файлов...")

    conn = None

    try:
        init_db()

        conn = get_connection()
        cur = conn.cursor()

        _set_metadata_cursor(cur, {
            "index_status": "building",
            "last_started_at": started_at,
            "last_finished_at": "",
            "last_error": "",
            "indexed_count": 0,
        })
        conn.commit()

        logger.info("Индексация | подготовка временной таблицы")
        _create_new_index_table(cur)
        conn.commit()

        buffer = []
        total_inserted = 0

        roots = get_priority_roots()
        ordered_sources = list(roots.keys())

        logger.info("Индексация | priority roots count=%s sources=%s", len(ordered_sources), ordered_sources)

        for source_kind in ordered_sources:
            root_path = roots.get(source_kind)

            if not root_path:
                logger.info("Индексация | root skipped empty | source=%s", source_kind)
                continue

            if not os.path.exists(root_path):
                logger.info("Индексация | root skipped missing | source=%s path=%s", source_kind, root_path)
                continue

            total_inserted = _walk_source(
                root_path=str(root_path),
                source_kind=source_kind,
                cur=cur,
                conn=conn,
                buffer=buffer,
                total_inserted=total_inserted,
            )

        drives = get_windows_drives()
        logger.info("Индексация | windows drives count=%s drives=%s", len(drives), drives)

        for drive in drives:
            if not os.path.exists(drive):
                continue

            total_inserted = _walk_source(
                root_path=str(drive),
                source_kind="global",
                cur=cur,
                conn=conn,
                buffer=buffer,
                total_inserted=total_inserted,
            )

        total_inserted = _insert_buffer(cur, conn, buffer, total_inserted)

        cur.execute("SELECT COUNT(*) FROM filesystem_index_new")
        final_count = int(cur.fetchone()[0])

        finished_at = _now_iso()
        elapsed = time.monotonic() - started

        logger.info(
            "Индексация | временный индекс готов | inserted=%s final_count=%s elapsed=%.2fs",
            total_inserted,
            final_count,
            elapsed,
        )

        logger.info("Индексация | атомарная замена старого индекса новым")

        conn.commit()
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("DROP TABLE IF EXISTS filesystem_index")
        cur.execute("ALTER TABLE filesystem_index_new RENAME TO filesystem_index")

        _create_filesystem_indexes(cur)

        _set_metadata_cursor(cur, {
            "index_status": "ready",
            "last_finished_at": finished_at,
            "last_error": "",
            "indexed_count": final_count,
            "last_rebuild_elapsed_sec": round(elapsed, 2),
        })

        conn.commit()

        index_state.finish(
            f"Индексация завершена. Объектов в индексе: {final_count}",
            indexed_count=final_count,
        )

        logger.info(
            "Индексация | rebuild_index finished | inserted=%s final_count=%s elapsed=%.2fs",
            total_inserted,
            final_count,
            elapsed,
        )

    except Exception as e:
        elapsed = time.monotonic() - started
        error_text = str(e)

        logger.exception("Индексация | rebuild_index failed | error=%s elapsed=%.2fs", error_text, elapsed)

        index_state.fail(
            message=f"Ошибка индексации: {error_text}",
            error=error_text,
        )

        try:
            set_index_metadata_many({
                "index_status": "failed",
                "last_finished_at": _now_iso(),
                "last_error": error_text,
                "last_rebuild_elapsed_sec": round(elapsed, 2),
            })
        except Exception as meta_error:
            logger.exception("Индексация | не удалось сохранить metadata ошибки: %s", meta_error)

        raise

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_index_count() -> int:
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM filesystem_index")
    count = int(cur.fetchone()[0])
    conn.close()
    return count