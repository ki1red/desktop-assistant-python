import re
from pathlib import Path


RU_TO_EN_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya"
}

EN_TO_RU_SPECIAL = {
    "ya": "я",
    "yu": "ю",
    "zh": "ж",
    "ch": "ч",
    "sh": "ш",
    "sch": "щ",
    "ts": "ц",
    "th": "т",
    "ea": "и",
    "ee": "и",
}

EXTENSION_ALIASES = {
    "pdf": ["pdf", "пдф"],
    "doc": ["doc", "док", "word", "ворд"],
    "docx": ["docx", "докс", "word", "ворд"],
    "xls": ["xls", "excel", "эксель"],
    "xlsx": ["xlsx", "excel", "эксель"],
    "ppt": ["ppt", "powerpoint", "паверпойнт"],
    "pptx": ["pptx", "powerpoint", "паверпойнт"],
    "txt": ["txt", "текст"],
    "mp3": ["mp3"],
    "wav": ["wav"],
    "png": ["png"],
    "jpg": ["jpg", "jpeg", "джипег"],
    "py": ["py", "python", "питон"],
    "lnk": ["shortcut", "ярлык"]
}

RU_VOWELS = set("аеёиоуыэюя")
EN_VOWELS = set("aeiouy")


def normalize_basic(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[._\-()\[\],!?;:+]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _simplify_russian_word(word: str) -> str:
    """
    Очень грубая нормализация окончаний для поискового match.
    Не лемматизация, а просто срез популярных падежных/числовых хвостов.
    """
    if len(word) <= 4:
        return word

    endings = [
        "иями", "ями", "ами", "ями",
        "ого", "ему", "ому", "ыми", "ими",
        "ия", "ий", "ие", "иям", "иях",
        "ов", "ев", "ом", "ем", "ам", "ям",
        "ах", "ях", "ую", "юю",
        "ой", "ей", "ый", "ий",
        "а", "я", "у", "ю", "е", "ы", "и", "о"
    ]

    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[:-len(ending)]

    return word


def normalize_query_text(text: str) -> str:
    text = normalize_basic(text)
    tokens = text.split()
    tokens = [_simplify_russian_word(t) for t in tokens]
    return normalize_basic(" ".join(tokens))


def translit_ru_to_en(text: str) -> str:
    result = []
    for ch in text.lower():
        result.append(RU_TO_EN_MAP.get(ch, ch))
    return "".join(result)


def translit_en_to_ru(text: str) -> str:
    text = text.lower()

    for en, ru in sorted(EN_TO_RU_SPECIAL.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(en, ru)

    table = {
        "a": "а", "b": "б", "c": "к", "d": "д", "e": "е",
        "f": "ф", "g": "г", "h": "х", "i": "и", "j": "дж",
        "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
        "p": "п", "q": "к", "r": "р", "s": "с", "t": "т",
        "u": "у", "v": "в", "w": "в", "x": "кс", "y": "й",
        "z": "з"
    }

    result = []
    for ch in text:
        result.append(table.get(ch, ch))
    return "".join(result)


def split_tokens(text: str) -> list[str]:
    return [t for t in normalize_basic(text).split() if t]


def consonant_skeleton(text: str) -> str:
    text = normalize_basic(text)
    out = []
    for ch in text:
        if ch == " ":
            out.append(ch)
            continue
        if ("а" <= ch <= "я" and ch not in RU_VOWELS) or ("a" <= ch <= "z" and ch not in EN_VOWELS):
            out.append(ch)
    return normalize_basic("".join(out))


def build_name_variants(name: str, parent_hint: str | None = None) -> set[str]:
    variants = set()

    raw = normalize_basic(name)
    if raw:
        variants.add(raw)
        variants.add(normalize_query_text(raw))

    path = Path(name)
    stem = normalize_basic(path.stem)
    if stem:
        variants.add(stem)
        variants.add(normalize_query_text(stem))

    suffix = path.suffix.lower().replace(".", "")
    if suffix:
        suffix_aliases = EXTENSION_ALIASES.get(suffix, [suffix])

        if stem:
            variants.add(f"{stem} {suffix}")
            variants.add(normalize_query_text(f"{stem} {suffix}"))
            for alias in suffix_aliases:
                variants.add(f"{stem} {alias}")
                variants.add(normalize_query_text(f"{stem} {alias}"))

    if parent_hint:
        parent_norm = normalize_basic(parent_hint)
        if parent_norm:
            variants.add(parent_norm)
            variants.add(normalize_query_text(parent_norm))
            if stem:
                variants.add(f"{parent_norm} {stem}")
                variants.add(normalize_query_text(f"{parent_norm} {stem}"))

    for base in list(variants):
        ru_to_en = normalize_basic(translit_ru_to_en(base))
        en_to_ru = normalize_basic(translit_en_to_ru(base))

        if ru_to_en:
            variants.add(ru_to_en)
        if en_to_ru:
            variants.add(en_to_ru)

    for base in list(variants):
        sk = consonant_skeleton(base)
        if sk:
            variants.add(sk)

    return {v for v in variants if v.strip()}


def build_search_blob(name: str, parent_hint: str | None = None) -> str:
    return " | ".join(sorted(build_name_variants(name, parent_hint)))