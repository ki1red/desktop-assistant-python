import os
from pathlib import Path

from app.models import ParsedCommand, ResolvedTarget
from app.resolver.app_index import find_best_app_matches
from app.resolver.file_search import detect_explicit_path, search_indexed_targets
from app.resolver.path_utils import looks_like_explicit_path, validate_path_step_by_step
from app.adaptive.history import get_direct_usage_match
from app.config import ASSISTANT_SETTINGS, USAGE_DIRECT_OPEN_SCORE


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

    def _debug_print(self, label: str, candidates):
        if not ASSISTANT_SETTINGS.get("debug_candidates", True):
            return

        print(f"[DEBUG] {label}:")
        for c in candidates[:5]:
            print(f"  - {c.name} | {c.score:.1f} | {c.path}")

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

    def _resolve_app(self, query: str):
        usage_hit = self._from_usage(query, ["app"], "generic_open")
        if usage_hit:
            return usage_hit

        app_candidates = find_best_app_matches(query)
        if app_candidates:
            self._debug_print("app candidates", app_candidates)

        if app_candidates and self._is_confident_enough(app_candidates):
            best = app_candidates[0]
            return ResolvedTarget(
                success=True,
                target_type=best.target_type,
                target_name=best.name,
                target_path=best.path,
                candidates=app_candidates
            )

        return None

    def _resolve_file(self, query: str):
        usage_hit = self._from_usage(query, ["file"], "generic_open")
        if usage_hit:
            return usage_hit

        file_candidates = search_indexed_targets(query, "file")
        if file_candidates:
            self._debug_print("file candidates", file_candidates)
            best = file_candidates[0]
            return ResolvedTarget(
                success=True,
                target_type=best.target_type,
                target_name=best.name,
                target_path=best.path,
                candidates=file_candidates
            )
        return None

    def _resolve_folder(self, query: str):
        usage_hit = self._from_usage(query, ["folder"], "generic_open")
        if usage_hit:
            return usage_hit

        folder_candidates = search_indexed_targets(query, "folder")
        if folder_candidates:
            self._debug_print("folder candidates", folder_candidates)
            best = folder_candidates[0]
            return ResolvedTarget(
                success=True,
                target_type=best.target_type,
                target_name=best.name,
                target_path=best.path,
                candidates=folder_candidates
            )
        return None

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

        if command.intent == "open_app":
            result = self._resolve_app(command.target_text)
            if result:
                return result
            return ResolvedTarget(success=False, error="Не удалось надежно определить приложение.")

        if command.intent == "open_file" or command.intent == "play_media":
            result = self._resolve_file(command.target_text)
            if result:
                return result
            return ResolvedTarget(success=False, error="Файл не найден.")

        if command.intent == "open_folder":
            result = self._resolve_folder(command.target_text)
            if result:
                return result
            return ResolvedTarget(success=False, error="Папка не найдена.")

        if command.intent == "generic_open":
            # Важный порядок: приложения -> файлы -> папки
            for resolver_fn in [self._resolve_app, self._resolve_file, self._resolve_folder]:
                result = resolver_fn(command.target_text)
                if result:
                    return result

            return ResolvedTarget(success=False, error="Не удалось определить, что именно открыть.")

        return ResolvedTarget(success=False, error="Неизвестная команда.")