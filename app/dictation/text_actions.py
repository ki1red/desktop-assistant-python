import time

import keyboard
import pyperclip


SPECIAL_PHRASES = {
    "новая строка": "\n",
    "новый абзац": "\n\n",
    "точка": ".",
    "запятая": ",",
    "двоеточие": ":",
    "точка с запятой": ";",
    "вопросительный знак": "?",
    "восклицательный знак": "!",
    "открывающая скобка": "(",
    "закрывающая скобка": ")",
    "открывающая кавычка": "\"",
    "закрывающая кавычка": "\"",
    "тире": " - ",
}


def normalize_dictation_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text.strip()

    for symbol in [".", ",", ";", ":", "?", "!"]:
        cleaned = cleaned.replace(f" {symbol}", symbol)

    return cleaned


def insert_text(text: str):
    if not text:
        return

    old_clipboard = None
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        old_clipboard = None

    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        time.sleep(0.05)
    finally:
        if old_clipboard is not None:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass


def apply_dictation_phrase(text: str) -> bool:
    normalized = text.strip().lower()

    if not normalized:
        return True

    if normalized == "стереть последнее слово":
        keyboard.send("ctrl+backspace")
        return True

    if normalized == "стереть":
        keyboard.send("backspace")
        return True

    if normalized in SPECIAL_PHRASES:
        insert_text(SPECIAL_PHRASES[normalized])
        return True

    insert_text(normalize_dictation_text(text))
    return True