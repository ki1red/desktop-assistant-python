import os
from pathlib import Path

from app.models import ParsedCommand, ResolvedTarget
from app.resolver.app_index import find_best_app_matches
from app.resolver.file_search import detect_explicit_path, search_indexed_targets
from app.resolver.path_utils import looks_like_explicit_path, validate_path_step_by_step
from app.adaptive.history import get_direct_usage_match
from app.config import ASSISTANT_SETTINGS, USAGE_DIRECT_OPEN_SCORE


class TargetResolver:
    def _debug_print(self, label: str, candidates):
        if not ASSISTANT_SETTINGS.get("debug_candidates", True):
            return

        print(f"[DEBUG] {label}:")
        for c in candidates[:5]:
            print(f"  - {c.name} | {c.score:.1f} | {c.path}")

    def _is_confident_enough(self, candidates):
        if not candidates:
            return False

        best = candidates[0]

        if len(candidates) == 1:
            return best.score >= 90

        second = candidates[1]

        if best.score >= 94:
            return True

        if best.score >= 90 and (best.score - second.score) >= 6:
            return True

        return False

    def _wrap_result(self, candidates, not_found_error: str):
        if not candidates:
            return ResolvedTarget(success=False, error=not_found_error)

        best = candidates[0]

        if self._is_confident_enough(candidates):
            return ResolvedTarget(
                success=True,
                target_type=best.target_type,
                target_name=best.name,
                target_path=best.path,
                candidates=candidates
            )

        return ResolvedTarget(
            success=False,
            target_type=best.target_type,
            target_name=best.name,
            target_path=best.path,
            candidates=candidates,
            needs_confirmation=True,
            confirmation_message=f"Я не совсем уверен. Возможно, ты имел в виду: {best.name}. Открыть это?"
        )

    def _from_usage(self, query: str, allowed_types: list[str], intent: str):
        usage_match = get_direct_usage_match(query, allowed_types, intent)
        if usage_match and usage_match["score"] >= USAGE_DIRECT_OPEN_SCORE:
            return ResolvedTarget(
                success=True,
                target_type=usage_match["target_type"],
                target_name=usage_match["name"],
                target_path=usage_match["path"]
            )
        return None

    def _resolve_app_candidates(self, query: str):
        usage_hit = self._from_usage(query, ["app"], "generic_open")
        if usage_hit:
            return [CandidateWrapper(usage_hit.target_name, usage_hit.target_path, usage_hit.target_type)]

        app_candidates = find_best_app_matches(query)
        if app_candidates:
            self._debug_print("app candidates", app_candidates)
        return app_candidates

    def _resolve_file_candidates(self, query: str, generic_mode: bool = False):
        usage_hit = self._from_usage(query, ["file"], "generic_open")
        if usage_hit:
            return [CandidateWrapper(usage_hit.target_name, usage_hit.target_path, usage_hit.target_type)]

        file_candidates = search_indexed_targets(query, "file", generic_mode=generic_mode)
        if file_candidates:
            self._debug_print("file candidates", file_candidates)
        return file_candidates

    def _resolve_folder_candidates(self, query: str):
        usage_hit = self._from_usage(query, ["folder"], "generic_open")
        if usage_hit:
            return [CandidateWrapper(usage_hit.target_name, usage_hit.target_path, usage_hit.target_type)]

        folder_candidates = search_indexed_targets(query, "folder", generic_mode=False)
        if folder_candidates:
            self._debug_print("folder candidates", folder_candidates)
        return folder_candidates

    def resolve(self, command: ParsedCommand) -> ResolvedTarget:
        if command.intent == "negative_feedback":
            return ResolvedTarget(success=False, error="negative_feedback")

        if not command.target_text and command.intent != "negative_feedback":
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

        if looks_like_explicit_path(command.target_text):
            ok, message = validate_path_step_by_step(command.target_text)
            if ok:
                target_type = "folder" if os.path.isdir(message) else "file"
                return ResolvedTarget(
                    success=True,
                    target_type=target_type,
                    target_name=Path(message).name,
                    target_path=message
                )
            return ResolvedTarget(success=False, error=message)

        if command.intent == "open_file" or command.intent == "play_media":
            candidates = self._resolve_file_candidates(command.target_text, generic_mode=False)
            return self._wrap_result(candidates, "Файл не найден.")

        if command.intent == "open_folder":
            candidates = self._resolve_folder_candidates(command.target_text)
            return self._wrap_result(candidates, "Папка не найдена.")

        if command.intent in ["open_app"]:
            candidates = self._resolve_app_candidates(command.target_text)
            return self._wrap_result(candidates, "Не удалось надежно определить приложение.")

        if command.intent == "generic_open":
            app_candidates = self._resolve_app_candidates(command.target_text)
            file_candidates = self._resolve_file_candidates(command.target_text, generic_mode=True)
            folder_candidates = self._resolve_folder_candidates(command.target_text)

            best_app = app_candidates[0] if app_candidates else None
            best_file = file_candidates[0] if file_candidates else None
            best_folder = folder_candidates[0] if folder_candidates else None

            if best_app and (
                not best_file or best_app.score >= best_file.score - 4
            ) and (
                not best_folder or best_app.score >= best_folder.score - 4
            ):
                return self._wrap_result(app_candidates, "Не удалось определить, что открыть.")

            if best_file and (
                not best_folder or best_file.score >= best_folder.score - 3
            ):
                return self._wrap_result(file_candidates, "Не удалось определить, что открыть.")

            if best_folder:
                return self._wrap_result(folder_candidates, "Не удалось определить, что открыть.")

            return ResolvedTarget(success=False, error="Не удалось определить, что именно открыть.")

        return ResolvedTarget(success=False, error="Неизвестная команда.")


class CandidateWrapper:
    def __init__(self, name, path, target_type):
        self.name = name
        self.path = path
        self.target_type = target_type
        self.score = 100.0