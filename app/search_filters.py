from pathlib import Path

from app.text_variants import normalize_basic


SAFE_OPEN_FILE_EXTENSIONS = {
    "txt", "pdf", "doc", "docx", "rtf", "odt",
    "xls", "xlsx", "csv",
    "ppt", "pptx",
    "mp3", "wav", "flac", "ogg",
    "mp4", "mkv", "avi", "mov",
    "png", "jpg", "jpeg", "bmp", "gif", "webp",
    "py", "cpp", "h", "hpp", "cs", "json", "yaml", "yml", "md", "ini"
}

BLOCKED_FILE_EXTENSIONS = {
    "dll", "sys", "res", "pak", "ttf", "ttc", "fon", "mui", "manifest",
    "cmake", "lib", "obj", "o", "pdb", "bin", "dat", "db", "tmp",
    "exp", "ilk", "pch", "idb", "ipdb", "iobj", "a", "so", "jar", "class"
}


def _extract_ext_from_path_or_name(value: str) -> str:
    return Path(value).suffix.lower().replace(".", "")


def is_short_junk_name(name: str) -> bool:
    n = normalize_basic(name)
    if not n:
        return True

    tokens = n.split()
    if len(tokens) == 1 and len(tokens[0]) <= 2:
        return True

    return False


def is_bad_generic_file_candidate(file_name: str, full_path: str = "") -> bool:
    stem = normalize_basic(Path(file_name).stem if Path(file_name).suffix else file_name)
    ext = _extract_ext_from_path_or_name(full_path or file_name)

    if is_short_junk_name(stem):
        return True

    if ext in BLOCKED_FILE_EXTENSIONS:
        return True

    return False


def is_safe_user_openable_file(file_name: str, full_path: str = "") -> bool:
    ext = _extract_ext_from_path_or_name(full_path or file_name)

    if ext in BLOCKED_FILE_EXTENSIONS:
        return False

    return ext in SAFE_OPEN_FILE_EXTENSIONS