import os
from pathlib import Path

from app.models import ParsedCommand, ResolvedTarget
from app.resolver.app_index import find_best_app_matches
from app.resolver.file_search import detect_explicit_path, search_files_prioritized


class TargetResolver:
    def _is_confident_enough(self, candidates):
        if not candidates:
            return False

        best = candidates[0]

        if len(candidates) == 1:
            return best.score >= 88

        second = candidates[1]

        if best.score >= 94:
            return True

        if best.score >= 86 and (best.score - second.score) >= 8:
            return True

        return False

    def resolve(self, command: ParsedCommand) -> ResolvedTarget:
        if not command.target_text:
            return ResolvedTarget(success=False, error="Не удалось выделить цель команды.")

        explicit_path = detect_explicit_path(command.target_text)
        if explicit_path:
            target_type = "folder" if os.path.isdir(explicit_path) else "file"
            return ResolvedTarget(
                success=True,
                target_type=target_type,
                target_name=Path(explicit_path).name,
                target_path=explicit_path
            )

        if command.intent == "open_app":
            app_candidates = find_best_app_matches(command.target_text, threshold=78)

            if app_candidates:
                print("[DEBUG] app candidates:")
                for c in app_candidates[:5]:
                    print(f"  - {c.name} | {c.score:.1f} | {c.path}")

            if app_candidates and self._is_confident_enough(app_candidates):
                best = app_candidates[0]
                return ResolvedTarget(
                    success=True,
                    target_type=best.target_type,
                    target_name=best.name,
                    target_path=best.path,
                    candidates=app_candidates
                )

            return ResolvedTarget(
                success=False,
                error="Не удалось надежно определить приложение."
            )

        if command.intent == "open_file" or command.intent == "play_media":
            file_candidates = search_files_prioritized(command.target_text, only_folders=False)

            if file_candidates:
                print("[DEBUG] file candidates:")
                for c in file_candidates[:5]:
                    print(f"  - {c.name} | {c.score:.1f} | {c.path}")

                best = file_candidates[0]
                return ResolvedTarget(
                    success=True,
                    target_type=best.target_type,
                    target_name=best.name,
                    target_path=best.path,
                    candidates=file_candidates
                )

            return ResolvedTarget(success=False, error="Файл не найден.")

        if command.intent == "open_folder":
            folder_candidates = search_files_prioritized(command.target_text, only_folders=True)

            if folder_candidates:
                print("[DEBUG] folder candidates:")
                for c in folder_candidates[:5]:
                    print(f"  - {c.name} | {c.score:.1f} | {c.path}")

                best = folder_candidates[0]
                return ResolvedTarget(
                    success=True,
                    target_type=best.target_type,
                    target_name=best.name,
                    target_path=best.path,
                    candidates=folder_candidates
                )

            return ResolvedTarget(success=False, error="Папка не найдена.")

        return ResolvedTarget(success=False, error="Неизвестная команда.")