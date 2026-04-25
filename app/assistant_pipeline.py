import threading
from multiprocessing import get_context
from queue import Empty

from app.speech.recorder import (
    record_audio_to_wav,
    delete_temp_file,
    MicrophoneSelectionError,
    NoMicrophoneSignalError,
)
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
from app.workers.resolve_worker import run_resolve_worker
from app.nlu.text_cleanup import cleanup_command_text
from app.nlu.resources_loader import nlu_resources
from app.dictation.ai_postprocess import apply_basic_dictation_replacements
from app.logger import get_logger

logger = get_logger("pipeline")

class OperationCancelled(Exception):
    pass


class AssistantPipeline:
    LONG_RESOLVE_INTENTS = {
        "generic_open",
        "open_file",
        "open_folder",
        "open_app",
    }

    def __init__(self):
        self.transcriber = SpeechTranscriber()
        self.parser = CommandParser()
        self.resolver = TargetResolver()
        self.executor = CommandExecutor()
        self.presenter = ResponsePresenter()
        self.notifier = AssistantNotifier()
        self.ai_gateway = AIGateway()

        self._ctx = get_context("spawn")
        self._resolve_process = None
        self._resolve_queue = None
        self._resolve_lock = threading.RLock()

    def _command_to_payload(self, command) -> dict:
        return {
            "text": getattr(command, "text", "")
                    or getattr(command, "raw_text", "")
                    or getattr(command, "source_text", "")
                    or getattr(command, "normalized_text", ""),
            "normalized_text": getattr(command, "normalized_text", ""),
            "intent": getattr(command, "intent", ""),
            "target_text": getattr(command, "target_text", ""),
        }

    def _clear_resolve_process(self):
        with self._resolve_lock:
            self._resolve_process = None
            self._resolve_queue = None

    def has_active_long_task(self) -> bool:
        with self._resolve_lock:
            return self._resolve_process is not None and self._resolve_process.is_alive()

    def cancel_current_operation(self):
        runtime_control.cancel_job()

        with self._resolve_lock:
            proc = self._resolve_process

        if proc is None:
            return

        if not proc.is_alive():
            self._clear_resolve_process()
            return

        try:
            proc.terminate()
            proc.join(timeout=1.5)
            if proc.is_alive():
                try:
                    proc.kill()
                    proc.join(timeout=1.0)
                except Exception:
                    pass
        finally:
            self._clear_resolve_process()

    def _resolve_command(self, command, deep_search: bool = False):
        if command.intent not in self.LONG_RESOLVE_INTENTS:
            return self.resolver.resolve(command, deep_search=deep_search)

        payload = self._command_to_payload(command)
        result_queue = self._ctx.Queue()
        process = self._ctx.Process(
            target=run_resolve_worker,
            args=(payload, deep_search, result_queue),
            daemon=True,
        )

        with self._resolve_lock:
            self._resolve_process = process
            self._resolve_queue = result_queue

        process.start()

        try:
            while True:
                if runtime_control.is_cancelled():
                    raise OperationCancelled()

                try:
                    status, data = result_queue.get(timeout=0.1)
                except Empty:
                    if not process.is_alive():
                        if process.exitcode == 0:
                            return ResolvedTarget(
                                success=False,
                                error="Не удалось получить результат поиска."
                            )
                        raise OperationCancelled()
                    continue

                if status == "ok":
                    return data

                return ResolvedTarget(
                    success=False,
                    error=f"Ошибка поиска: {data}"
                )
        finally:
            if process.is_alive():
                try:
                    process.join(timeout=0.2)
                except Exception:
                    pass
            self._clear_resolve_process()

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

            try:
                resolved = self._resolve_command(command, deep_search=deep_search)
            except OperationCancelled:
                print("[PIPELINE] Долгая операция была отменена.")
                return ExecutionResult(
                    success=False,
                    message="Операция отменена пользователем.",
                    intent=command.intent
                )

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

    def _handle_dictation(self, text: str):
        if runtime_control.is_cancelled():
            return None

        parsed = self.parser.parse(text)

        if parsed.intent == "disable_dictation":
            execution = self.executor.execute(parsed, ResolvedTarget(success=False))
            self.presenter.show(execution)
            return execution

        if parsed.intent == "enable_dictation":
            execution = self.executor.execute(parsed, ResolvedTarget(success=False))
            self.presenter.show(execution)
            return execution

        text = apply_basic_dictation_replacements(text)
        ai_cfg = settings_service.get_section("ai", {})
        if ai_cfg.get("enabled", False) and ai_cfg.get("apply_to_all_commands", False):
            if ai_cfg.get("refine_dictation", False):
                ai_result = self.ai_gateway.refine_dictation_text(
                    text,
                    rules={
                        "dictation_replacements": nlu_resources.dictation_replacements
                    },
                    context=[]
                )
                if ai_result and ai_result.get("normalized_text"):
                    text = ai_result["normalized_text"].strip()
                    logger.info("Диктовка после AI refine: %s", text)

        apply_dictation_phrase(text)
        logger.info("DICTATION inserted: %s", text)
        message = f"Продиктовано: {text}"
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
        logger.info("Начало цикла обработки команды.")
        wav_path = None

        def normalize_ai_intent_hint(value: str | None) -> str | None:
            if not value:
                return None

            v = str(value).strip().lower()

            allowed = {
                "enable_chat_mode",
                "disable_chat_mode",
                "enable_dictation",
                "disable_dictation",
                "open_file",
                "open_folder",
                "generic_open",
                "search_web",
                "search_youtube",
                "play_music_query",
                "select_candidate",
                "unknown",
            }

            return v if v in allowed else None

        try:
            try:
                wav_path = record_audio_to_wav()
            except (MicrophoneSelectionError, NoMicrophoneSignalError) as e:
                msg = str(e)
                logger.warning("Ошибка микрофона: %s", msg)
                self.notifier.say(msg)
                return None
            except Exception as e:
                logger.exception("Не удалось начать запись: %s", e)
                self.notifier.say("Не удалось начать запись с микрофона.")
                return None

            if runtime_control.is_cancelled():
                logger.info("Операция отменена пользователем сразу после записи.")
                self.notifier.say("Операция отменена.")
                return None

            if not dictation_state.is_enabled() and not chat_state.is_enabled():
                self.notifier.say_random("processing")

            try:
                stt_result = self.transcriber.transcribe(wav_path)
            except Exception as e:
                logger.exception("Ошибка распознавания аудио: %s", e)
                if not dictation_state.is_enabled() and not chat_state.is_enabled():
                    self.notifier.say("Не удалось распознать аудио.")
                return None

            if runtime_control.is_cancelled():
                logger.info("Операция отменена пользователем после STT.")
                if not dictation_state.is_enabled() and not chat_state.is_enabled():
                    self.notifier.say("Операция отменена.")
                return None

            print(f"[STT] {stt_result.text}")
            logger.info("Распознанный текст: %s", stt_result.text)
            logger.info("Язык распознавания: %s", stt_result.language)

            if dictation_state.is_enabled():
                return self._handle_dictation(stt_result.text)

            if chat_state.is_enabled():
                return self._handle_chat_mode(stt_result.text)

            cleaned_text = cleanup_command_text(stt_result.text)
            logger.info("Текст после базовой очистки: %s", cleaned_text)

            final_text = cleaned_text
            ai_intent_hint = None
            target_hint = None
            entity_type_hint = None

            ai_cfg = settings_service.get_section("ai", {})
            logger.info(
                "AI flags: enabled=%s apply_to_all_commands=%s provider=%s",
                ai_cfg.get("enabled", False),
                ai_cfg.get("apply_to_all_commands", False),
                ai_cfg.get("provider", "unknown"),
            )

            if ai_cfg.get("enabled", False) and ai_cfg.get("apply_to_all_commands", False):
                logger.info("Запуск AI refine для команды.")
                ai_result = self.ai_gateway.refine_command_text(
                    cleaned_text,
                    rules={
                        "polite_words": nlu_resources.polite_words,
                        "filler_words": nlu_resources.filler_words,
                        "command_verbs": nlu_resources.command_verbs,
                        "extension_aliases": nlu_resources.extension_aliases,
                    }
                )

                logger.info("AI refine_command result: %s", ai_result)

                if ai_result:
                    if ai_result.get("normalized_text"):
                        final_text = ai_result["normalized_text"].strip()

                    ai_intent_hint = normalize_ai_intent_hint(ai_result.get("intent_hint"))
                    target_hint = ai_result.get("target_hint")
                    entity_type_hint = ai_result.get("entity_type_hint")

                    logger.info(
                        "Текст после AI refine: %s | raw_intent_hint=%s | normalized_intent_hint=%s | target_hint=%s | entity_type_hint=%s | confidence=%s",
                        final_text,
                        ai_result.get("intent_hint"),
                        ai_intent_hint,
                        target_hint,
                        entity_type_hint,
                        ai_result.get("confidence"),
                    )

            command = self.parser.parse(final_text)
            parser_intent = command.intent
            logger.info("PARSER returned intent=%s target=%s", command.intent, command.target_text)

            special_parser_intents = {
                "enable_chat_mode",
                "disable_chat_mode",
                "enable_dictation",
                "disable_dictation",
                "select_candidate",
                "confirm_deep_search",
                "reject_deep_search",
                "custom_command",
                "negative_feedback",
            }

            target_override_allowed_intents = {
                "generic_open",
                "open_file",
                "open_folder",
                "search_web",
                "search_youtube",
                "play_music_query",
            }

            if parser_intent in special_parser_intents:
                logger.info("AI override пропущен: parser уже распознал специальный intent=%s", parser_intent)
            else:
                if ai_intent_hint:
                    logger.info("Применяю AI intent_hint=%s вместо parser intent=%s", ai_intent_hint, parser_intent)
                    command.intent = ai_intent_hint

                if target_hint and command.intent in target_override_allowed_intents:
                    logger.info("Применяю AI target_hint=%s", target_hint)
                    command.target_text = str(target_hint).strip()

            logger.info("PARSED intent=%s target=%s", command.intent, command.target_text)
            print(f"[PARSED] intent={command.intent}, target={command.target_text}")

            if runtime_control.is_cancelled():
                logger.info("Операция отменена пользователем после parse.")
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
                    logger.info("Нет запроса на глубокий поиск.")
                    self.notifier.say("Нет запроса на глубокий поиск.")
                    return None
                return self._handle_command(pending, deep_search=True)

            if command.intent == "reject_deep_search":
                return self._handle_command(command, deep_search=False)

            return self._handle_command(command, deep_search=False)

        finally:
            if wav_path and TEMP_CLEANUP_SETTINGS.get("delete_record_after_transcribe", True):
                delete_temp_file(wav_path)
            print("[PIPELINE] Цикл обработки завершён.")
            logger.info("Цикл обработки завершён.")