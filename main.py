from app.indexing.db import init_db
from app.indexing.indexer import rebuild_index, get_index_count
from app.adaptive.history import init_history_tables
from app.speech.recorder import cleanup_old_temp_files
from app.assistant_pipeline import AssistantPipeline


def bootstrap():
    print("=== Local PC Assistant ===")

    init_db()
    init_history_tables()
    cleanup_old_temp_files()

    count = get_index_count()
    if count == 0:
        print("[INDEX] Индекс пуст. Начинаю первичную индексацию...")
        rebuild_index()
        count = get_index_count()
        print(f"[INDEX] Готово. В индексе объектов: {count}")


def main():
    bootstrap()

    pipeline = AssistantPipeline()

    print("Нажми Enter, чтобы записать голосовую команду...")
    input()
    pipeline.run_once()


if __name__ == "__main__":
    main()