from app.models import ParsedCommand
from app.resolver.resolver import TargetResolver


def run_resolve_worker(command_payload: dict, deep_search: bool, result_queue):
    try:
        command = ParsedCommand(
            command_payload.get("text", ""),
            command_payload.get("normalized_text", ""),
            command_payload.get("intent", ""),
            command_payload.get("target_text", ""),
        )

        resolver = TargetResolver()
        resolved = resolver.resolve(command, deep_search=deep_search)
        result_queue.put(("ok", resolved))
    except Exception as e:
        result_queue.put(("error", str(e)))