from app.indexing.db import init_db
from app.indexing.indexer import rebuild_index, get_index_count

print("[INDEX] Инициализация БД...")
init_db()

print("[INDEX] Перестройка индекса...")
rebuild_index()

print(f"[INDEX] Готово. Всего объектов: {get_index_count()}")