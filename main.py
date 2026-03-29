from app.speech.recorder import record_audio_to_wav
from app.speech.transcriber import SpeechTranscriber
from app.nlu.parser import CommandParser
from app.resolver.resolver import TargetResolver
from app.executor.executor import CommandExecutor
from app.response.presenter import ResponsePresenter
from app.indexing.indexer import rebuild_index, get_index_count


def main():
    print("=== Local PC Assistant ===")

    count = get_index_count()
    if count == 0:
        print("[INDEX] Индекс пуст. Начинаю первичную индексацию...")
        rebuild_index()
        count = get_index_count()
        print(f"[INDEX] Готово. В индексе объектов: {count}")

    print("Нажми Enter, чтобы записать голосовую команду...")
    input()

    wav_path = record_audio_to_wav(duration_sec=5)

    transcriber = SpeechTranscriber()
    parser = CommandParser()
    resolver = TargetResolver()
    executor = CommandExecutor()
    presenter = ResponsePresenter()

    stt_result = transcriber.transcribe(wav_path)
    print(f"[STT] {stt_result.text}")

    command = parser.parse(stt_result.text)
    print(f"[PARSED] intent={command.intent}, target={command.target_text}")

    resolved = resolver.resolve(command)
    print(f"[RESOLVED] success={resolved.success}, type={resolved.target_type}, path={resolved.target_path}")

    execution = executor.execute(command, resolved)
    presenter.show(execution)


if __name__ == "__main__":
    main()