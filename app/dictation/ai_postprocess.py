from app.nlu.resources_loader import nlu_resources


def apply_basic_dictation_replacements(text: str) -> str:
    result = text
    for src, dst in sorted(nlu_resources.dictation_replacements.items(), key=lambda x: len(x[0]), reverse=True):
        result = result.replace(src, dst)
        result = result.replace(src.capitalize(), dst)
    return result