import os
from pathlib import Path
from typing import List, Optional

from app.models import Candidate
from app.scoring import score_candidate
from app.utils import get_windows_drives, get_priority_roots


def detect_explicit_path(text: str) -> Optional[str]:
    text = text.strip().strip('"')
    if os.path.exists(text):
        return text
    return None


def _search_in_root(root_path: str, query: str, only_folders: bool, source_kind: str) -> List[Candidate]:
    results: List[Candidate] = []

    if not root_path or not os.path.exists(root_path):
        return results

    for root, dirs, files in os.walk(root_path, topdown=True):
        dirs[:] = [
            d for d in dirs
            if d.lower() not in {
                "windows",
                "program files",
                "program files (x86)",
                "$recycle.bin",
                "system volume information"
            }
        ]

        try:
            if only_folders:
                for folder_name in dirs:
                    score = score_candidate(query, folder_name, source_kind)
                    if score >= 78:
                        full_path = str(Path(root) / folder_name)
                        results.append(Candidate(
                            name=folder_name,
                            path=full_path,
                            score=score,
                            target_type="folder"
                        ))
            else:
                for file_name in files:
                    score = score_candidate(query, file_name, source_kind)
                    if score >= 78:
                        full_path = str(Path(root) / file_name)
                        results.append(Candidate(
                            name=file_name,
                            path=full_path,
                            score=score,
                            target_type="file"
                        ))
        except PermissionError:
            continue
        except OSError:
            continue

    return results


def search_files_prioritized(query: str, only_folders: bool = False) -> List[Candidate]:
    results: List[Candidate] = []
    roots = get_priority_roots()

    ordered_sources = ["cwd", "desktop", "documents", "downloads", "recent"]

    for source_kind in ordered_sources:
        path = roots.get(source_kind)
        results.extend(_search_in_root(path, query, only_folders, source_kind))

    # fallback — полный поиск по всем дискам
    for drive in get_windows_drives():
        results.extend(_search_in_root(drive, query, only_folders, "global"))

    # убираем дубликаты по path
    unique = {}
    for item in results:
        if item.path not in unique or item.score > unique[item.path].score:
            unique[item.path] = item

    final_results = list(unique.values())
    final_results.sort(key=lambda x: x.score, reverse=True)
    return final_results[:20]