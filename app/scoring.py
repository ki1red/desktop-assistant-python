from rapidfuzz import fuzz

from app.text_variants import build_name_variants, normalize_basic, split_tokens
from app.adaptive.history import get_usage_bonus


SOURCE_WEIGHTS = {
    "cwd": 12,
    "desktop": 10,
    "recent": 6,
    "documents": 8,
    "downloads": 7,
    "start_menu_user": 10,
    "start_menu_common": 8,
    "global": 0,
}


def _length_penalty(query_variant: str, candidate_variant: str) -> float:
    q_len = max(len(query_variant), 1)
    c_len = max(len(candidate_variant), 1)

    ratio = c_len / q_len

    if ratio <= 1.8:
        return 0.0
    if ratio <= 3.0:
        return 4.0
    if ratio <= 5.0:
        return 10.0
    return 18.0


def _technical_name_penalty(candidate_variant: str) -> float:
    penalty = 0.0

    if "." in candidate_variant:
        penalty += 4.0

    upper_chunks = sum(1 for ch in candidate_variant if ch.isdigit())
    if upper_chunks >= 3:
        penalty += 3.0

    long_tokens = [t for t in split_tokens(candidate_variant) if len(t) >= 12]
    if long_tokens:
        penalty += 5.0

    return penalty


def score_candidate(query: str, candidate_name: str, source_kind: str = "global", target_path: str = "") -> float:
    q = normalize_basic(query)
    if not q:
        return 0

    query_variants = build_name_variants(q)
    candidate_variants = build_name_variants(candidate_name)

    best = 0.0
    q_tokens_root = set(split_tokens(q))

    for qv in query_variants:
        qv_tokens = set(split_tokens(qv))

        for cv in candidate_variants:
            cv_tokens = set(split_tokens(cv))
            score = 0.0

            if qv == cv:
                score = max(score, 100)

            if cv.startswith(qv):
                score = max(score, 95)

            # Полное покрытие токенов запроса
            if qv_tokens and cv_tokens and qv_tokens.issubset(cv_tokens):
                score = max(score, 92)

            # Совпадение целого токена
            if qv in cv_tokens:
                score = max(score, 91)

            # Подстрока разрешена, но слабее
            if qv in cv:
                score = max(score, 82)

            if qv_tokens and cv_tokens:
                inter = qv_tokens & cv_tokens
                if inter:
                    token_ratio = (len(inter) / max(len(qv_tokens), len(cv_tokens))) * 100
                    score = max(score, 68 + token_ratio * 0.22)

            ratio = fuzz.ratio(qv, cv)
            token_sort = fuzz.token_sort_ratio(qv, cv)
            token_set = fuzz.token_set_ratio(qv, cv)

            # partial_ratio — только ограниченно
            if len(qv) >= 5 and len(cv) <= len(qv) * 3:
                partial = fuzz.partial_ratio(qv, cv)
                score = max(score, ratio, token_sort, token_set, partial)
            else:
                score = max(score, ratio, token_sort, token_set)

            # Бонус за короткое "чистое" имя
            if len(cv_tokens) <= 3 and len(cv) <= len(qv) * 2:
                score += 3.0

            # Штраф, если совпало только одно короткое слово внутри длинной штуки
            if len(qv_tokens) <= 1 and len(cv_tokens) >= 3:
                score -= 6.0

            score -= _length_penalty(qv, cv)
            score -= _technical_name_penalty(cv)

            if score > best:
                best = score

    best += SOURCE_WEIGHTS.get(source_kind, 0)

    if target_path:
        best += get_usage_bonus(q, target_path)

    return max(0.0, min(best, 100.0))