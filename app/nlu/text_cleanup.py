import re

from app.nlu.resources_loader import nlu_resources


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def remove_polite_and_filler_words(text: str) -> str:
    t = f" {normalize_spaces(text).lower()} "

    for word in sorted(nlu_resources.polite_words + nlu_resources.filler_words, key=len, reverse=True):
        pattern = r"(?<!\w)" + re.escape(word.lower()) + r"(?!\w)"
        t = re.sub(pattern, " ", t)

    return normalize_spaces(t)


def normalize_extensions(text: str) -> str:
    t = normalize_spaces(text)
    low = t.lower()

    for src, dst in nlu_resources.extension_aliases.items():
        low = re.sub(r"(?<!\w)" + re.escape(src.lower()) + r"(?!\w)", dst.lower(), low)

    return normalize_spaces(low)


def cleanup_command_text(text: str) -> str:
    t = normalize_spaces(text)
    t = remove_polite_and_filler_words(t)
    t = normalize_extensions(t)
    return normalize_spaces(t)