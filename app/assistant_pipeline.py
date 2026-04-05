from app.speech.recorder import record_audio_to_wav, delete_temp_file
from app.speech.transcriber import SpeechTranscriber
from app.nlu.parser import CommandParser
from app.resolver.resolver import TargetResolver
from app.executor.executor import CommandExecutor
from app.response.presenter import ResponsePresenter
from app.adaptive.history import save_usage
from app.adaptive.quick_access import upsert_quick_target
from app.session.state import session_state
from app.config import RECORD_DURATION_SEC, TEMP_CLEANUP_SETTINGS


class AssistantPipeline:
    def __init__(self):
        self.transcriber = SpeechTranscriber()
        self.parser = CommandParser()
        self.resolver = TargetResolver()
        self.executor = CommandExecutor()
        self.presenter = ResponsePresenter()

    def _handle_command(self, command, deep_search: bool = False):
        resolved = self.resolver.resolve(command, deep_search=deep_search)
        print(f"[RESOLVED] success={resolved.success}, type={resolved.target_type}, path={resolved.target_path}")

        execution = self.executor.execute(command, resolved)
        self.presenter.show(execution)

        if resolved.suggests_deep_search:
            session_state.set_pending_deep_search(command)
        else:
            session_state.clear_pending_deep_search()

        save_usage(
            query_text=command.target_text,
            intent=command.intent,
            target_name=resolved.target_name or "",
            target_path=resolved.target_path or "",
            target_type=resolved.target_type or "",
            success=execution.success
        )

        if execution.success and resolved.target_path and resolved.target_name and resolved.target_type:
            upsert_quick_target(
                name=resolved.target_name,
                target_path=resolved.target_path,
                target_type=resolved.target_type,
                provider="local",
                increment_usage=True
            )

        session_state.remember(command, resolved, execution)
        return execution

    def run_once(self):
        wav_path = record_audio_to_wav(duration_sec=RECORD_DURATION_SEC)

        try:
            try:
                stt_result = self.transcriber.transcribe(wav_path)
            except Exception as e:
                print(f"[STT][ERROR] Не удалось распознать аудио: {e}")
                return None

            print(f"[STT] {stt_result.text}")

            command = self.parser.parse(stt_result.text)
            print(f"[PARSED] intent={command.intent}, target={command.target_text}")

            if command.intent == "confirm_deep_search":
                pending = session_state.pending_deep_search_command
                if pending is None:
                    print("[INFO] Нет запроса на глубокий поиск.")
                    return None
                return self._handle_command(pending, deep_search=True)

            if command.intent == "reject_deep_search":
                return self._handle_command(command, deep_search=False)

            return self._handle_command(command, deep_search=False)

        finally:
            if TEMP_CLEANUP_SETTINGS.get("delete_record_after_transcribe", True):
                delete_temp_file(wav_path)