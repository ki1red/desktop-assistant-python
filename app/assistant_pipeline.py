from app.speech.recorder import record_audio_to_wav, delete_temp_file
from app.speech.transcriber import SpeechTranscriber
from app.nlu.parser import CommandParser
from app.resolver.resolver import TargetResolver
from app.executor.executor import CommandExecutor
from app.response.presenter import ResponsePresenter
from app.adaptive.history import save_usage
from app.adaptive.quick_access import upsert_quick_target
from app.session.state import session_state
from app.config import TEMP_CLEANUP_SETTINGS
from app.models import ResolvedTarget, ExecutionResult
from app.events.notifier import AssistantNotifier
from app.assistant_progress import ProgressHeartbeat
from app.runtime_control import runtime_control
from app.dictation.state import dictation_state
from app.dictation.text_actions import apply_dictation_phrase
from app.chat.state import chat_state
from app.ai.gateway import AIGateway
from app.settings_service import settings_service


class AssistantPipeline:
    def __init__(self):
        self.transcriber = SpeechTranscriber()
        self.parser = CommandParser()
        self.resolver = TargetResolver()
        self.executor = CommandExecutor()
        self.presenter = ResponsePresenter()
        self.notifier = AssistantNotifier()
        self.ai_gateway = AIGateway()

    def _handle_command(self, command, deep_search: bool = False):
        if runtime_control.is_cancelled():
            print("[PIPELINE] Операция отменена пользователем до начала выполнения.")
            self.notifier.say("Операция отменена.")
            return None

        heartbeat = ProgressHeartbeat()
        heartbeat.start()
        try:
            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем перед resolve.")
                self.notifier.say("Операция отменена.")
                return None

            resolved = self.resolver.resolve(command, deep_search=deep_search)
            print(f"[RESOLVED] success={resolved.success}, type={resolved.target_type}, path={resolved.target_path}")

            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем после resolve.")
                return None

            execution = self.executor.execute(command, resolved)
            self.presenter.show(execution)

            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем после execute.")
                return None

            if resolved.suggests_deep_search:
                session_state.set_pending_deep_search(command)
            else:
                session_state.clear_pending_deep_search()

            if resolved.needs_confirmation and resolved.candidates:
                session_state.set_pending_candidates(command, resolved.candidates)
            else:
                session_state.clear_pending_candidates()

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
        finally:
            heartbeat.stop()

    def _handle_selection(self, selected_index: int):
        pending_command = session_state.pending_selection_command
        pending_candidates = session_state.pending_candidates

        if pending_command is None or not pending_candidates:
            print("[PIPELINE] Нет вариантов для выбора.")
            self.notifier.say("Нет вариантов для выбора.")
            return None

        idx = selected_index - 1
        if idx < 0 or idx >= len(pending_candidates):
            print("[PIPELINE] Неверный номер варианта.")
            self.notifier.say("Неверный номер варианта.")
            return None

        chosen = pending_candidates[idx]
        resolved = ResolvedTarget(
            success=True,
            target_type=chosen.target_type,
            target_name=chosen.name,
            target_path=chosen.path,
            candidates=pending_candidates
        )

        print(f"[RESOLVED] success={resolved.success}, type={resolved.target_type}, path={resolved.target_path}")

        execution = self.executor.execute(pending_command, resolved)
        self.presenter.show(execution)

        save_usage(
            query_text=pending_command.target_text,
            intent=pending_command.intent,
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

        session_state.clear_pending_candidates()
        session_state.clear_pending_deep_search()
        session_state.remember(pending_command, resolved, execution)
        return execution

    def _handle_dictation(self, stt_text: str):
        if runtime_control.is_cancelled():
            return None

        parsed = self.parser.parse(stt_text)

        if parsed.intent == "disable_dictation":
            execution = self.executor.execute(parsed, ResolvedTarget(success=False))
            self.presenter.show(execution)
            return execution

        if parsed.intent == "enable_dictation":
            execution = self.executor.execute(parsed, ResolvedTarget(success=False))
            self.presenter.show(execution)
            return execution

        apply_dictation_phrase(stt_text)
        message = f"Продиктовано: {stt_text}"
        print(f"[DICTATION] {message}")

        return ExecutionResult(
            success=True,
            message=message,
            intent="dictation_text"
        )

    def _handle_chat_mode(self, stt_text: str):
        parsed = self.parser.parse(stt_text)

        if parsed.intent == "disable_chat_mode":
            execution = self.executor.execute(parsed, ResolvedTarget(success=False))
            self.presenter.show(execution)
            return execution

        if parsed.intent == "enable_chat_mode":
            execution = self.executor.execute(parsed, ResolvedTarget(success=False))
            self.presenter.show(execution)
            return execution

        reply = self.ai_gateway.ask(stt_text)
        print(f"[AI] {reply}")

        if settings_service.get_section("ai", {}).get("speak_responses", True):
            self.notifier.say(reply)

        return ExecutionResult(
            success=True,
            message=reply,
            intent="chat_reply"
        )

    def run_once(self):
        print("[PIPELINE] Начало цикла обработки команды.")
        wav_path = record_audio_to_wav()

        try:
            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем сразу после записи.")
                self.notifier.say("Операция отменена.")
                return None

            if not dictation_state.is_enabled() and not chat_state.is_enabled():
                self.notifier.say_random("processing")

            try:
                stt_result = self.transcriber.transcribe(wav_path)
            except Exception as e:
                print(f"[STT][ERROR] Не удалось распознать аудио: {e}")
                if not dictation_state.is_enabled() and not chat_state.is_enabled():
                    self.notifier.say("Не удалось распознать аудио.")
                return None

            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем после STT.")
                if not dictation_state.is_enabled() and not chat_state.is_enabled():
                    self.notifier.say("Операция отменена.")
                return None

            print(f"[STT] {stt_result.text}")

            if dictation_state.is_enabled():
                return self._handle_dictation(stt_result.text)

            if chat_state.is_enabled():
                return self._handle_chat_mode(stt_result.text)

            command = self.parser.parse(stt_result.text)
            print(f"[PARSED] intent={command.intent}, target={command.target_text}")

            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем после parse.")
                self.notifier.say("Операция отменена.")
                return None

            if command.intent == "enable_chat_mode":
                return self._handle_command(command, deep_search=False)

            if command.intent == "disable_chat_mode":
                return self._handle_command(command, deep_search=False)

            if command.intent == "select_candidate":
                return self._handle_selection(int(command.target_text))

            if command.intent == "confirm_deep_search":
                pending = session_state.pending_deep_search_command
                if pending is None:
                    print("[PIPELINE] Нет запроса на глубокий поиск.")
                    self.notifier.say("Нет запроса на глубокий поиск.")
                    return None
                return self._handle_command(pending, deep_search=True)

            if command.intent == "reject_deep_search":
                return self._handle_command(command, deep_search=False)

            return self._handle_command(command, deep_search=False)

        finally:
            if TEMP_CLEANUP_SETTINGS.get("delete_record_after_transcribe", True):
                delete_temp_file(wav_path)
            print("[PIPELINE] Цикл обработки завершён.")