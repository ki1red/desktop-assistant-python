import threading
from multiprocessing import get_context
from queue import Empty

from app.speech.recorder import (
    record_audio_to_wav,
    delete_temp_file,
    MicrophoneSelectionError,
    NoMicrophoneSignalError,
)
from app.speech.transcriber import SpeechTranscriber, NoSpeechDetected
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
from app.plugins.settings import is_plugin_enabled


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

    INTENT_PLUGIN_COMMAND_MAP = {
        "open_file": ("filesystem", "open_file"),
        "open_folder": ("filesystem", "open_folder"),
        "open_app": ("filesystem", "open_app"),
        "generic_open": ("filesystem", "open_anything"),

        "search_web": ("web", "search_web"),
        "search_youtube": ("web", "search_youtube"),

        "play_music_query": ("music", "play_music_query"),

        "enable_dictation": ("dictation", "enable_dictation"),
        "disable_dictation": ("dictation", "disable_dictation"),

        "enable_chat_mode": ("chat", "enable_chat_mode"),
        "disable_chat_mode": ("chat", "disable_chat_mode"),
    }

    SPECIAL_PARSER_INTENTS = {
        "enable_chat_mode",
        "disable_chat_mode",
        "enable_dictation",
        "disable_dictation",
        "custom_command",
        "negative_feedback",
        "incomplete_command",
    }

    TARGET_OVERRIDE_ALLOWED_INTENTS = {
        "generic_open",
        "open_file",
        "open_folder",
        "search_web",
        "search_youtube",
        "play_music_query",
    }

    AI_ALLOWED_INTENT_HINTS = {
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
        "unknown",
    }

    DO_NOT_SAVE_USAGE_INTENTS = {
        "unknown",
        "incomplete_command",
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
        """
        Подготавливает команду для отдельного процесса resolve.
        """
        return {
            "text": getattr(command, "text", "")
                    or getattr(command, "raw_text", "")
                    or getattr(command, "source_text", "")
                    or getattr(command, "normalized_text", ""),
            "raw_text": getattr(command, "raw_text", ""),
            "normalized_text": getattr(command, "normalized_text", ""),
            "intent": getattr(command, "intent", ""),
            "target_text": getattr(command, "target_text", ""),
            "plugin_id": getattr(command, "plugin_id", None),
            "command_id": getattr(command, "command_id", None),
            "confidence": getattr(command, "confidence", 0.0),
            "metadata": getattr(command, "metadata", {}) or {},
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

    def _normalize_ai_intent_hint(self, value: str | None) -> str | None:
        """
        Приводит intent_hint от ИИ к безопасному внутреннему intent.
        """
        if not value:
            return None

        normalized = str(value).strip().lower()

        if normalized in self.AI_ALLOWED_INTENT_HINTS:
            return normalized

        return None

    def _sync_command_plugin_fields(self, command):
        """
        Синхронизирует plugin_id/command_id после AI override.
        """
        plugin_id, command_id = self.INTENT_PLUGIN_COMMAND_MAP.get(
            command.intent,
            (None, None),
        )

        command.plugin_id = plugin_id
        command.command_id = command_id

        if not hasattr(command, "metadata") or command.metadata is None:
            command.metadata = {}

        if plugin_id:
            command.metadata["plugin_id"] = plugin_id
        if command_id:
            command.metadata["command_id"] = command_id

        return command

    def _sync_runtime_modes_with_plugins(self):
        """
        Страховка на случай, если runtime state остался включён,
        а сам plugin уже выключен в settings.
        """
        if chat_state.is_enabled() and not is_plugin_enabled("chat", True):
            logger.info("Chat runtime mode сброшен в pipeline: plugin chat отключён.")
            chat_state.disable()

        if dictation_state.is_enabled() and not is_plugin_enabled("dictation", True):
            logger.info("Dictation runtime mode сброшен в pipeline: plugin dictation отключён.")
            dictation_state.disable()

    def _is_chat_mode_active(self) -> bool:
        self._sync_runtime_modes_with_plugins()
        return chat_state.is_enabled()

    def _is_dictation_mode_active(self) -> bool:
        self._sync_runtime_modes_with_plugins()
        return dictation_state.is_enabled()

    def _resolve_command(self, command, deep_search: bool = False):
        """
        Выполняет resolve.

        Долгий локальный поиск запускается в отдельном процессе.
        Сервисные команды вроде web/music/chat/dictation resolver обработает быстро.
        """
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
                                error="Не удалось получить результат поиска.",
                            )

                        raise OperationCancelled()

                    continue

                if status == "ok":
                    return data

                return ResolvedTarget(
                    success=False,
                    error=f"Ошибка поиска: {data}",
                )

        finally:
            if process.is_alive():
                try:
                    process.join(timeout=0.2)
                except Exception:
                    pass

            self._clear_resolve_process()

    def _save_usage_if_needed(self, command, resolved, execution):
        """
        Сохраняет историю использования только для нормальных команд.
        """
        if command.intent in self.DO_NOT_SAVE_USAGE_INTENTS:
            return

        save_usage(
            query_text=command.target_text,
            intent=command.intent,
            target_name=resolved.target_name or "",
            target_path=resolved.target_path or "",
            target_type=resolved.target_type or "",
            success=execution.success,
        )

        if execution.success and resolved.target_path and resolved.target_name and resolved.target_type:
            upsert_quick_target(
                name=resolved.target_name,
                target_path=resolved.target_path,
                target_type=resolved.target_type,
                provider=command.plugin_id or "local",
                increment_usage=True,
            )

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
                    intent=command.intent,
                )

            print(
                f"[RESOLVED] success={resolved.success}, "
                f"type={resolved.target_type}, path={resolved.target_path}"
            )

            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем после resolve.")
                return None

            execution = self.executor.execute(command, resolved)
            self.presenter.show(execution)

            if runtime_control.is_cancelled():
                print("[PIPELINE] Операция отменена пользователем после execute.")
                return None

            # На каждом выполнении чистим старые сценарии подтверждений.
            session_state.clear_pending_all()

            self._save_usage_if_needed(command, resolved, execution)

            session_state.remember(command, resolved, execution)
            return execution

        finally:
            heartbeat.stop()

    def _handle_selection(self, selected_index: int):
        """
        Старый обработчик выбора кандидата.

        Теперь выбор "первый/второй/третий" отключён.
        Метод оставлен только для совместимости, но новая логика его не вызывает.
        """
        print("[PIPELINE] Выбор вариантов отключён. Resolver выбирает первый вариант автоматически.")
        self.notifier.say("Выбор вариантов отключён. Я выбираю лучший вариант автоматически.")
        session_state.clear_pending_all()
        return None

    def _handle_dictation(self, text: str):
        if runtime_control.is_cancelled():
            return None

        parsed = self.parser.parse(text)

        if parsed.intent == "disable_dictation":
            execution = self.executor.execute(parsed, ResolvedTarget(success=True, target_type="service"))
            self.presenter.show(execution)
            return execution

        if parsed.intent == "enable_dictation":
            execution = self.executor.execute(parsed, ResolvedTarget(success=True, target_type="service"))
            self.presenter.show(execution)
            return execution

        text = apply_basic_dictation_replacements(text)

        ai_cfg = settings_service.get_section("ai", {})

        if ai_cfg.get("enabled", False) and ai_cfg.get("apply_to_all_commands", False):
            if ai_cfg.get("refine_dictation", False):
                ai_result = self.ai_gateway.refine_dictation_text(
                    text,
                    rules={
                        "dictation_replacements": nlu_resources.dictation_replacements,
                    },
                    context=[],
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
            intent="dictation_text",
        )

    def _handle_chat_mode(self, stt_text: str):
        parsed = self.parser.parse(stt_text)

        if parsed.intent == "disable_chat_mode":
            execution = self.executor.execute(parsed, ResolvedTarget(success=True, target_type="service"))
            self.presenter.show(execution)
            return execution

        if parsed.intent == "enable_chat_mode":
            execution = self.executor.execute(parsed, ResolvedTarget(success=True, target_type="service"))
            self.presenter.show(execution)
            return execution

        reply = self.ai_gateway.ask(stt_text)
        print(f"[AI] {reply}")

        if settings_service.get_section("ai", {}).get("speak_responses", True):
            self.notifier.say(reply)

        return ExecutionResult(
            success=True,
            message=reply,
            intent="chat_reply",
        )

    def _apply_ai_refine(self, cleaned_text: str) -> tuple[str, str | None, str | None, str | None]:
        """
        Запускает AI refine для обычной команды.
        """
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

        if not ai_cfg.get("enabled", False):
            return final_text, ai_intent_hint, target_hint, entity_type_hint

        if not ai_cfg.get("apply_to_all_commands", False):
            return final_text, ai_intent_hint, target_hint, entity_type_hint

        logger.info("Запуск AI refine для команды.")

        ai_result = self.ai_gateway.refine_command_text(
            cleaned_text,
            rules={
                "polite_words": nlu_resources.polite_words,
                "filler_words": nlu_resources.filler_words,
                "command_verbs": nlu_resources.command_verbs,
                "extension_aliases": nlu_resources.extension_aliases,
            },
        )

        logger.info("AI refine_command result: %s", ai_result)

        if not ai_result:
            return final_text, ai_intent_hint, target_hint, entity_type_hint

        if ai_result.get("normalized_text"):
            final_text = ai_result["normalized_text"].strip()

        ai_intent_hint = self._normalize_ai_intent_hint(ai_result.get("intent_hint"))
        target_hint = ai_result.get("target_hint")
        entity_type_hint = ai_result.get("entity_type_hint")

        logger.info(
            "Текст после AI refine: %s | raw_intent_hint=%s | "
            "normalized_intent_hint=%s | target_hint=%s | "
            "entity_type_hint=%s | confidence=%s",
            final_text,
            ai_result.get("intent_hint"),
            ai_intent_hint,
            target_hint,
            entity_type_hint,
            ai_result.get("confidence"),
        )

        return final_text, ai_intent_hint, target_hint, entity_type_hint

    def _apply_ai_override_to_command(
        self,
        command,
        parser_intent: str,
        ai_intent_hint: str | None,
        target_hint,
    ):
        """
        Осторожно применяет intent_hint и target_hint от ИИ.
        """
        if parser_intent in self.SPECIAL_PARSER_INTENTS:
            logger.info(
                "AI override пропущен: parser уже распознал специальный intent=%s",
                parser_intent,
            )
            return command

        if ai_intent_hint and ai_intent_hint != "unknown":
            logger.info(
                "Применяю AI intent_hint=%s вместо parser intent=%s",
                ai_intent_hint,
                parser_intent,
            )
            command.intent = ai_intent_hint
            self._sync_command_plugin_fields(command)

        if target_hint and command.intent in self.TARGET_OVERRIDE_ALLOWED_INTENTS:
            logger.info("Применяю AI target_hint=%s", target_hint)
            command.target_text = str(target_hint).strip()

        return command

    def run_text(
        self,
        text: str,
        language: str | None = None,
        source: str = "text",
        announce_processing: bool = False,
    ):
        """
        Выполняет уже распознанный текст.
        """
        if runtime_control.is_cancelled():
            logger.info("Операция отменена пользователем до обработки текста.")
            return None

        try:
            self.notifier.stop_speaking()
        except Exception as e:
            logger.debug("Не удалось остановить TTS перед run_text: %s", e)

        raw_text = (text or "").strip()

        if not raw_text:
            logger.info("run_text получил пустой текст. source=%s", source)
            return None

        logger.info(
            "run_text | source=%s | language=%s | text=%s",
            source,
            language,
            raw_text,
        )

        print(f"[STT] {raw_text}")
        logger.info("Распознанный текст: %s", raw_text)

        if language:
            logger.info("Язык распознавания: %s", language)

        if self._is_dictation_mode_active():
            return self._handle_dictation(raw_text)

        if self._is_chat_mode_active():
            return self._handle_chat_mode(raw_text)

        if announce_processing:
            self.notifier.say_random("processing")

        cleaned_text = cleanup_command_text(raw_text)
        logger.info("Текст после базовой очистки: %s", cleaned_text)

        final_text, ai_intent_hint, target_hint, _entity_type_hint = self._apply_ai_refine(cleaned_text)

        command = self.parser.parse(final_text)
        parser_intent = command.intent

        logger.info(
            "PARSER returned intent=%s target=%s plugin=%s command=%s confidence=%s",
            command.intent,
            command.target_text,
            getattr(command, "plugin_id", None),
            getattr(command, "command_id", None),
            getattr(command, "confidence", None),
        )

        command = self._apply_ai_override_to_command(
            command=command,
            parser_intent=parser_intent,
            ai_intent_hint=ai_intent_hint,
            target_hint=target_hint,
        )

        logger.info(
            "PARSED intent=%s target=%s plugin=%s command=%s confidence=%s",
            command.intent,
            command.target_text,
            getattr(command, "plugin_id", None),
            getattr(command, "command_id", None),
            getattr(command, "confidence", None),
        )

        print(f"[PARSED] intent={command.intent}, target={command.target_text}")

        if runtime_control.is_cancelled():
            logger.info("Операция отменена пользователем после parse.")
            self.notifier.say("Операция отменена.")
            return None

        # Старые голосовые подтверждения больше не обрабатываем.
        # Если parser когда-нибудь вернёт такие intent из старого кода,
        # они попадут в обычный resolver и будут безопасно отклонены.
        return self._handle_command(command, deep_search=False)

    def run_once(self):
        """
        Полный цикл:
        запись аудио -> STT -> run_text().
        """
        print("[PIPELINE] Начало цикла обработки команды.")
        logger.info("Начало цикла обработки команды.")

        try:
            self.notifier.stop_speaking()
        except Exception as e:
            logger.debug("Не удалось остановить TTS перед run_once: %s", e)

        wav_path = None

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

            if not self._is_dictation_mode_active() and not self._is_chat_mode_active():
                self.notifier.say_random("processing")

            try:
                stt_result = self.transcriber.transcribe(wav_path)

            except NoSpeechDetected as e:
                logger.warning("Речь не распознана: %s", e)
                print(f"[STT][WARN] Речь не распознана: {e}")

                if not self._is_dictation_mode_active() and not self._is_chat_mode_active():
                    self.notifier.say("Я почти ничего не услышал. Попробуйте сказать команду чуть громче.")

                return None

            except Exception as e:
                logger.exception("Ошибка распознавания аудио: %s", e)
                print(f"[STT][ERROR] Не удалось распознать аудио: {e}")

                if not self._is_dictation_mode_active() and not self._is_chat_mode_active():
                    self.notifier.say("Не удалось распознать аудио.")

                return None

            if runtime_control.is_cancelled():
                logger.info("Операция отменена пользователем после STT.")

                if not self._is_dictation_mode_active() and not self._is_chat_mode_active():
                    self.notifier.say("Операция отменена.")

                return None

            return self.run_text(
                text=stt_result.text,
                language=stt_result.language,
                source="voice_record",
                announce_processing=False,
            )

        finally:
            if wav_path and TEMP_CLEANUP_SETTINGS.get("delete_record_after_transcribe", True):
                delete_temp_file(wav_path)

            print("[PIPELINE] Цикл обработки завершён.")
            logger.info("Цикл обработки завершён.")