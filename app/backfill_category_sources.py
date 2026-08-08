import argparse
import sys

from app.db import get_connection


def preview_category_sources() -> dict:
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        source_counts = conn.execute("""
            SELECT category_source, COUNT(*)
            FROM items
            GROUP BY category_source
        """).fetchall()
    return {
        "total_items": total,
        "source_counts": dict(source_counts),
        "note": "Старые ручные изменения нельзя восстановить достоверно: audit log отсутствовал. Скрипт ничего не меняет.",
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args()

    result = preview_category_sources()
    print(f"Всего items: {result['total_items']}")
    print("category_source:")
    for source, count in sorted(result["source_counts"].items()):
        print(f"  {source}: {count}")
    print(result["note"])


if __name__ == "__main__":
    main()
