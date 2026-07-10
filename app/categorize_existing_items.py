import re
from collections import Counter

from app.category_keywords import categorize_from_name
from app.db import get_connection


def is_valid_item_name(name: str) -> bool:
    if not name:
        return False

    name = name.strip().lower()
    if len(name) < 3:
        return False
    if name in {"g", "ml", "gab", "gab.", "kg", "l", "l.", "1", "2"}:
        return False

    return re.fullmatch(r"\d+(g|ml|gab|kg|l)\.?", name) is None


def categorize_all_items(overwrite: bool = False):
    with get_connection() as conn:
        cursor = conn.cursor()
        if overwrite:
            cursor.execute("SELECT id, name FROM items")
        else:
            cursor.execute("SELECT id, name FROM items WHERE category IS NULL OR category = ''")

        items = cursor.fetchall()
        category_counter = Counter()

        for item_id, name in items:
            category = categorize_from_name(name) if is_valid_item_name(name) else "прочее"
            category_counter[category] += 1
            cursor.execute("UPDATE items SET category = ? WHERE id = ?", (category, item_id))

        conn.commit()

    return category_counter


if __name__ == "__main__":
    stats = categorize_all_items(overwrite=True)
    print("Категоризация завершена.")
    for category, count in stats.most_common():
        print(f"{category}: {count}")
