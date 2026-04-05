import os
from pathlib import Path
from typing import List, Optional, Set

from rapidfuzz import fuzz

from app.models import Candidate
from app.indexing.db import get_connection
from app.config import APP_MATCH_THRESHOLD, MAX_CANDIDATES, PRIORITY_CONFIDENT_SCORE
from app.text_variants import (
    normalize_basic,
    build_name_variants,
    split_tokens,
    normalize_query_text,
)
from app.utils import get_priority_roots


def _build_priority_app_sources() -> set[str]:
    roots = set(get_priority_roots().keys())
    roots.discard("documents")
    roots.discard("downloads")
    roots.discard("recent")
    return roots


def _fetch_app_rows_prefiltered(query: str, source_kinds: Optional[Set[str]] = None, limit: int = 300):
    conn = get_connection()
    cur = conn.cursor()

    conditions = ["target_type = 'app'"]
    params = []

    if source_kinds:
        placeholders = ",".join("?" for _ in source_kinds)
        conditions.append(f"source_kind IN ({placeholders})")
        params.extend(list(source_kinds))

    variant_conditions = []
    for variant in sorted(build_name_variants(query)):
        v = normalize_basic(variant)
        if len(v) >= 2:
            variant_conditions.append("search_blob LIKE ?")
            params.append(f"%{v}%")

    if variant_conditions:
        conditions.append("(" + " OR ".join(variant_conditions[:8]) + ")")

    sql = f"""
        SELECT path, name, target_type, source_kind, normalized_name, search_blob, parent_path
        FROM filesystem_index
        WHERE {' AND '.join(conditions)}
        LIMIT {limit}
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def _variant_similarity(query_text: str, candidate_text: str) -> float:
    q_variants = build_name_variants(query_text)
    c_variants = build_name_variants(candidate_text)

    best = 0.0
    for qv in q_variants:
        for cv in c_variants:
            score = max(
                fuzz.ratio(qv, cv),
                fuzz.token_sort_ratio(qv, cv),
                fuzz.token_set_ratio(qv, cv)
            )
            if qv == cv:
                score = max(score, 100.0)
            best = max(best, score)
    return best


def _token_penalty(query_text: str, candidate_text: str) -> float:
    q_tokens = split_tokens(normalize_query_text(query_text))
    c_tokens = split_tokens(normalize_query_text(candidate_text))

    if not q_tokens or not c_tokens:
        return 0.0

    q_set = set(q_tokens)
    c_set = set(c_tokens)

    extra_tokens = c_set - q_set
    missing_tokens = q_set - c_set

    penalty = 0.0
    penalty += len(extra_tokens) * 22.0
    penalty += len(missing_tokens) * 24.0
    return penalty


def _length_penalty(query_text: str, candidate_text: str) -> float:
    q = normalize_query_text(query_text)
    c = normalize_query_text(candidate_text)

    diff = abs(len(c) - len(q))
    if diff <= 1:
        return 0.0
    if diff <= 4:
        return diff * 2.0
    return 8.0 + (diff - 4) * 1.2


def _single_token_exact_bonus(query_text: str, candidate_text: str) -> float:
    """
    Если запрос однословный, однословный кандидат должен сильно побеждать
    кандидатов с хвостами вроде 'Яндекс.Диск' или 'Яндекс Музыка'.
    """
    q_tokens = split_tokens(normalize_query_text(query_text))
    c_tokens = split_tokens(normalize_query_text(candidate_text))

    if len(q_tokens) != 1:
        return 0.0

    if len(c_tokens) != 1:
        return 0.0

    q_variants = build_name_variants(query_text)
    c_variants = build_name_variants(candidate_text)

    if any(qv == cv for qv in q_variants for cv in c_variants):
        return 26.0

    return 0.0


def _exact_variant_bonus(query_text: str, candidate_text: str) -> float:
    q_variants = build_name_variants(query_text)
    c_variants = build_name_variants(candidate_text)

    q_norm = normalize_query_text(query_text)
    c_norm = normalize_query_text(candidate_text)

    if q_norm == c_norm:
        return 32.0

    if any(qv == cv for qv in q_variants for cv in c_variants):
        return 20.0

    if c_norm.startswith(q_norm):
        return 8.0

    return 0.0


def _score_single_app_candidate(query: str, row) -> float:
    name = row["name"]
    path = row["path"]
    source_kind = row["source_kind"]
    parent_path = row["parent_path"] or ""

    path_lower = path.lower()
    if source_kind == "recent":
        return 0.0

    if not (
        path_lower.endswith(".exe") or
        path_lower.endswith(".lnk") or
        path_lower.endswith(".url")
    ):
        return 0.0

    query_norm = normalize_query_text(query)
    name_norm = normalize_query_text(name)
    parent_name = Path(parent_path).name if parent_path else ""
    parent_norm = normalize_query_text(parent_name)
    path_norm = normalize_basic(path)

    score = _variant_similarity(query, name)
    score += _exact_variant_bonus(query, name)
    score += _single_token_exact_bonus(query, name)

    score -= _token_penalty(query_norm, name_norm)
    score -= _length_penalty(query_norm, name_norm)

    # Start Menu / Programs — полезный, но умеренный бонус
    if "start menu" in path_lower or "\\programs\\" in path_lower:
        score += 4.0

    # Совпадение в пути — небольшой бонус
    if query_norm and query_norm in path_norm:
        score += 2.0

    # Контекст родительской папки полезен, но не должен перебивать имя
    if parent_name:
        parent_combo = f"{parent_name} {name}"
        parent_score = _variant_similarity(query, parent_combo)
        parent_score += _exact_variant_bonus(query, parent_combo)
        parent_score -= _token_penalty(query_norm, normalize_query_text(parent_combo))
        parent_score -= _length_penalty(query_norm, normalize_query_text(parent_combo))
        score = max(score, parent_score - 10.0)

    browser_query = "браузер" in query_norm or "browser" in query_norm
    if browser_query:
        bad_subapps = ["почта", "музыка", "диск", "mail", "music", "disk"]
        if any(marker in name_norm for marker in bad_subapps):
            score -= 30.0
        if any(marker in parent_norm for marker in bad_subapps):
            score -= 24.0

        browser_markers = ["browser", "браузер"]
        if any(marker in path_norm for marker in browser_markers):
            score += 14.0
        if any(marker in parent_norm for marker in browser_markers):
            score += 10.0
        if any(marker in name_norm for marker in browser_markers):
            score += 10.0

    return max(0.0, min(score, 120.0))


def _score_rows(query: str, rows) -> List[Candidate]:
    results = []
    for row in rows:
        score = _score_single_app_candidate(query, row)
        if score >= APP_MATCH_THRESHOLD:
            results.append(Candidate(
                name=row["name"],
                path=row["path"],
                score=score,
                target_type=row["target_type"]
            ))

    results.sort(key=lambda x: (-x.score, len(x.name), x.name.lower()))
    return results[:MAX_CANDIDATES]


def _fallback_scan_apps(query: str) -> List[Candidate]:
    roots = get_priority_roots()
    results = []

    for source_kind, root_path in roots.items():
        if not root_path or not os.path.exists(root_path):
            continue

        try:
            for root, _, files in os.walk(root_path):
                for f in files:
                    if not f.lower().endswith((".lnk", ".url", ".exe")):
                        continue

                    full_path = str(Path(root) / f)
                    name = Path(f).stem
                    row_like = {
                        "name": name,
                        "path": full_path,
                        "source_kind": source_kind,
                        "parent_path": str(Path(full_path).parent),
                        "target_type": "app"
                    }

                    score = _score_single_app_candidate(query, row_like)
                    if score >= APP_MATCH_THRESHOLD:
                        results.append(Candidate(
                            name=name,
                            path=full_path,
                            score=score,
                            target_type="app"
                        ))
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: (-x.score, len(x.name), x.name.lower()))
    return results[:MAX_CANDIDATES]


def find_best_app_matches(query: str) -> List[Candidate]:
    priority_sources = _build_priority_app_sources()

    priority_rows = _fetch_app_rows_prefiltered(query, priority_sources, limit=250)
    priority_results = _score_rows(query, priority_rows)

    if priority_results and priority_results[0].score >= PRIORITY_CONFIDENT_SCORE:
        return priority_results

    all_rows = _fetch_app_rows_prefiltered(query, None, limit=500)
    all_results = _score_rows(query, all_rows)

    if all_results:
        return all_results

    return _fallback_scan_apps(query)