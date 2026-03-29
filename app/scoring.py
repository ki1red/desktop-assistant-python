from rapidfuzz import fuzz

from app.text_variants import build_name_variants, normalize_basic, split_tokens
from app.adaptive.history import get_usage_bonus


SOURCE_WEIGHTS = {
    "cwd": 12,
    "desktop": 10,
    "recent": 9,
    "documents": 8,
    "downloads": 7,
    "start_menu_user": 10,
    "start_menu_common": 8,
    "global": 0,
}


def score_candidate(query: str, candidate_name: str, source_kind: str = "global", target_path: str = "") -> float:
    q = normalize_basic(query)
    if not q:
        return 0

    query_variants = build_name_variants(q)
    candidate_variants = build_name_variants(candidate_name)

    best = 0.0
    q_tokens = set(split_tokens(q))

    for qv in query_variants:
        qv_tokens = set(split_tokens(qv))

        for cv in candidate_variants:
            cv_tokens = set(split_tokens(cv))
            score = 0.0

            if qv == cv:
                score = max(score, 100)

            if cv.startswith(qv):
                score = max(score, 95)

            if qv in cv:
                score = max(score, 90)

            if qv_tokens and cv_tokens:
                inter = qv_tokens & cv_tokens
                if inter:
                    token_ratio = (len(inter) / max(len(qv_tokens), len(cv_tokens))) * 100
                    score = max(score, 70 + token_ratio * 0.2)

                    if qv_tokens.issubset(cv_tokens):
                        score = max(score, 92)

            score = max(
                score,
                fuzz.ratio(qv, cv),
                fuzz.token_sort_ratio(qv, cv),
                fuzz.token_set_ratio(qv, cv)
            )

            if len(qv_tokens) == 1 and len(cv_tokens) >= 2 and list(qv_tokens)[0] in cv_tokens:
                score -= 6

            if score > best:
                best = score

    best += SOURCE_WEIGHTS.get(source_kind, 0)

    if target_path:
        best += get_usage_bonus(q, target_path)

    return min(best, 100)