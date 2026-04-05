from app.indexing.db import get_connection, init_db


def main():
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    patterns = ["%яндекс%", "%yandex%", "%browser%", "%браузер%"]

    print("=== APP DEBUG ===")
    for pattern in patterns:
        print(f"\n--- pattern: {pattern} ---")
        cur.execute("""
            SELECT name, path, source_kind, parent_path, search_blob
            FROM filesystem_index
            WHERE target_type = 'app'
              AND (
                    lower(name) LIKE lower(?)
                 OR lower(path) LIKE lower(?)
                 OR lower(search_blob) LIKE lower(?)
              )
            ORDER BY source_kind, name
            LIMIT 100
        """, (pattern, pattern, pattern))

        rows = cur.fetchall()
        if not rows:
            print("ничего не найдено")
            continue

        for row in rows:
            print(f"name       : {row['name']}")
            print(f"source_kind: {row['source_kind']}")
            print(f"path       : {row['path']}")
            print(f"parent     : {row['parent_path']}")
            print(f"search_blob: {row['search_blob']}")
            print("-" * 80)

    conn.close()


if __name__ == "__main__":
    main()