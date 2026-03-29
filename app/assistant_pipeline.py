from app.speech.recorder import record_audio_to_wav, delete_temp_file
from app.speech.transcriber import SpeechTranscriber
from app.nlu.parser import CommandParser
from app.resolver.resolver import TargetResolver
from app.executor.executor import CommandExecutor
from app.response.presenter import ResponsePresenter
from app.adaptive.history import save_usage
from app.session.state import session_state
from app.config import RECORD_DURATION_SEC, TEMP_CLEANUP_SETTINGS


class AssistantPipeline:
    def __init__(self):
        self.transcriber = SpeechTranscriber()
        self.parser = CommandParser()
        self.resolver = TargetResolver()
        self.executor = CommandExecutor()
        self.presenter = ResponsePresenter()

    def run_once(self):
        wav_path = record_audio_to_wav(duration_sec=RECORD_DURATION_SEC)

        try:
            stt_result = self.transcriber.transcribe(wav_path)
            print(f"[STT] {stt_result.text}")

            command = self.parser.parse(stt_result.text)
            print(f"[PARSED] intent={command.intent}, target={command.target_text}")

            resolved = self.resolver.resolve(command)
            print(f"[RESOLVED] success={resolved.success}, type={resolved.target_type}, path={resolved.target_path}")

            execution = self.executor.execute(command, resolved)
            self.presenter.show(execution)

            save_usage(
                query_text=command.target_text,
                intent=command.intent,
                target_name=resolved.target_name or "",
                target_path=resolved.target_path or "",
                target_type=resolved.target_type or "",
                success=execution.success
            )

            session_state.remember(command, resolved, execution)
            return execution

        finally:
            if TEMP_CLEANUP_SETTINGS.get("delete_record_after_transcribe", True):
                delete_temp_file(wav_path)