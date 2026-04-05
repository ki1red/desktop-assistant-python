from app.text_variants import normalize_basic


def normalize_command_text(text: str) -> str:
    """
    Для команд используем мягкую нормализацию:
    - lowercase
    - убрать пунктуацию
    - схлопнуть пробелы
    Но НЕ режем окончания, иначе ломаются ключевые слова
    вроде "открой" и "запусти".
    """
    return normalize_basic(text)