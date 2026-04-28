import os
import sqlite3
from pathlib import Path
from typing import List, Optional

from app.models import Candidate
from app.indexing.db import get_connection
from app.scoring import score_candidate
from app.config import FILE_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.utils import get_priority_roots
from app.text_variants import build_name_variants, normalize_basic
from app.search_filters import is_bad_generic_file_candidate, is_safe_user_openable_file
from app.runtime_control import runtime_control


def _build_priority_source_kinds() -> set[str]:
    keys = set(get_priority_roots().keys())
    keys.discard("start_menu_user")
    keys.discard("start_menu_common")
    return keys


def detect_explicit_path(text: str) -> Optional[str]:
    text = text.strip().strip('"')
    if os.path.exists(text):
        return text
    return None


def _fetch_candidates_by_type_prefiltered(
    wanted_type: str,
    query: str,
    source_kinds: Optional[set[str]] = None,
    limit: int = 400
):
    """
    Берёт из индекса кандидатов нужного типа.

    Важно:
    количество LIKE-условий и params должно совпадать.
    Раньше SQL использовал только первые 8 variant_conditions,
    но params содержал все варианты. Это давало ошибку SQLite:
    Incorrect number of bindings supplied.
    """
    conn = get_connection()
    cur = conn.cursor()

    conditions = ["target_type = ?"]
    params = [wanted_type]

    if source_kinds:
        placeholders = ",".join("?" for _ in source_kinds)
        conditions.append(f"source_kind IN ({placeholders})")
        params.extend(list(source_kinds))

    variants = []
    for variant in sorted(build_name_variants(query)):
        normalized_variant = normalize_basic(variant)
        if len(normalized_variant) >= 2:
            variants.append(normalized_variant)

    variant_conditions = []
    for variant in variants[:8]:
        variant_conditions.append("search_blob LIKE ?")
        params.append(f"%{variant}%")

    if variant_conditions:
        conditions.append("(" + " OR ".join(variant_conditions) + ")")

    sql = f"""
        SELECT path, name, target_type, source_kind, extension, normalized_name, search_blob
        FROM filesystem_index
        WHERE {' AND '.join(conditions)}
        LIMIT {int(limit)}
    """

    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        return rows
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            print("[SEARCH] SQL-поиск отменён пользователем.")
            return []
        raise
    finally:
        conn.close()


def _score_rows(query: str, rows, generic_mode: bool = False) -> List[Candidate]:
    results = []

    for row in rows:
        if runtime_control.is_cancelled():
            print("[SEARCH] Поиск отменён пользователем.")
            return []

        name = row["name"]
        full_path = row["path"]

        if generic_mode and row["target_type"] == "file":
            if is_bad_generic_file_candidate(name, full_path):
                continue
            if not is_safe_user_openable_file(name, full_path):
                continue

        score = score_candidate(query, name, row["source_kind"], full_path)

        if score >= FILE_MATCH_THRESHOLD:
            results.append(Candidate(
                name=name,
                path=full_path,
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def _fallback_scan_priority_roots(
    query: str,
    wanted_type: str,
    generic_mode: bool = False,
    max_found: int = 20
) -> List[Candidate]:
    roots = get_priority_roots()
    results = []

    for source_kind, root_path in roots.items():
        if runtime_control.is_cancelled():
            print("[SEARCH] Поиск отменён пользователем.")
            return []

        if not root_path or not os.path.exists(root_path):
            continue

        try:
            for root, dirs, files in os.walk(root_path):
                if runtime_control.is_cancelled():
                    print("[SEARCH] Поиск отменён пользователем.")
                    return []

                if wanted_type == "folder":
                    for folder_name in dirs:
                        if runtime_control.is_cancelled():
                            print("[SEARCH] Поиск отменён пользователем.")
                            return []

                        full_path = str(Path(root) / folder_name)
                        score = score_candidate(query, folder_name, source_kind, full_path)

                        if score >= FILE_MATCH_THRESHOLD:
                            results.append(Candidate(
                                name=folder_name,
                                path=full_path,
                                score=score,
                                target_type="folder"
                            ))

                            if len(results) >= max_found:
                                return sorted(results, key=lambda x: x.score, reverse=True)[:MAX_CANDIDATES]

                elif wanted_type == "file":
                    for file_name in files:
                        if runtime_control.is_cancelled():
                            print("[SEARCH] Поиск отменён пользователем.")
                            return []

                        full_path = str(Path(root) / file_name)

                        if generic_mode:
                            if is_bad_generic_file_candidate(file_name, full_path):
                                continue
                            if not is_safe_user_openable_file(file_name, full_path):
                                continue

                        score = score_candidate(query, file_name, source_kind, full_path)

                        if score >= FILE_MATCH_THRESHOLD:
                            results.append(Candidate(
                                name=file_name,
                                path=full_path,
                                score=score,
                                target_type="file"
                            ))

                            if len(results) >= max_found:
                                return sorted(results, key=lambda x: x.score, reverse=True)[:MAX_CANDIDATES]

        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:MAX_CANDIDATES]


def search_indexed_targets(
    query: str,
    wanted_type: str,
    generic_mode: bool = False,
    deep_search: bool = False
) -> List[Candidate]:
    if runtime_control.is_cancelled():
        print("[SEARCH] Поиск отменён пользователем.")
        return []

    priority_source_kinds = _build_priority_source_kinds()

    priority_rows = _fetch_candidates_by_type_prefiltered(
        wanted_type=wanted_type,
        query=query,
        source_kinds=priority_source_kinds,
        limit=200 if not deep_search else 350
    )
    priority_results = _score_rows(query, priority_rows, generic_mode=generic_mode)

    if runtime_control.is_cancelled():
        print("[SEARCH] Поиск отменён пользователем.")
        return []

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    if not deep_search:
        if priority_results:
            return priority_results

        return _fallback_scan_priority_roots(
            query,
            wanted_type,
            generic_mode=generic_mode,
            max_found=12
        )

    all_rows = _fetch_candidates_by_type_prefiltered(
        wanted_type=wanted_type,
        query=query,
        source_kinds=None,
        limit=500
    )
    all_results = _score_rows(query, all_rows, generic_mode=generic_mode)

    if runtime_control.is_cancelled():
        print("[SEARCH] Поиск отменён пользователем.")
        return []

    if all_results:
        return all_results

    return _fallback_scan_priority_roots(
        query,
        wanted_type,
        generic_mode=generic_mode,
        max_found=30
    )