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
}


EXTENSION_ALIASES = {
    "pdf": ["pdf", "пдф"],
    "doc": ["doc", "док"],
    "docx": ["docx", "докс", "ворд", "word"],
    "xls": ["xls", "эксель", "excel"],
    "xlsx": ["xlsx", "эксель", "excel"],
    "ppt": ["ppt", "паверпойнт", "powerpoint"],
    "pptx": ["pptx", "паверпойнт", "powerpoint"],
    "txt": ["txt", "текст"],
    "mp3": ["mp3", "эмпэтри"],
    "wav": ["wav", "вейв"],
    "png": ["png", "пнг"],
    "jpg": ["jpg", "jpeg", "джипег"],
    "py": ["py", "python", "питон"],
}


def normalize_basic(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[._\-()\[\],!?;:+]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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


def build_name_variants(name: str) -> set[str]:
    """
    Делает набор вариантов имени:
    - нормализованная форма
    - форма без расширения
    - транслит в обе стороны
    - расширение как слово
    """
    variants = set()

    raw = normalize_basic(name)
    if raw:
        variants.add(raw)

    path = Path(name)
    stem = normalize_basic(path.stem)
    if stem:
        variants.add(stem)

    suffix = path.suffix.lower().replace(".", "")
    if suffix:
        suffix_aliases = EXTENSION_ALIASES.get(suffix, [suffix])

        if stem:
            variants.add(f"{stem} {suffix}")
            for alias in suffix_aliases:
                variants.add(f"{stem} {alias}")

    for base in list(variants):
        ru_to_en = normalize_basic(translit_ru_to_en(base))
        en_to_ru = normalize_basic(translit_en_to_ru(base))

        if ru_to_en:
            variants.add(ru_to_en)
        if en_to_ru:
            variants.add(en_to_ru)

    return {v for v in variants if v.strip()}