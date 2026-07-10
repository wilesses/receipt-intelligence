import argparse
import sys

from app.db import get_connection
from app.product_normalizer import normalize_product_name


def backfill_normalized_names(dry_run: bool = False) -> dict:
    stats = {"checked": 0, "updated": 0, "skipped": 0, "errors": 0}

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, name
            FROM items
            WHERE normalized_name IS NULL OR TRIM(normalized_name) = ''
            ORDER BY id
        """).fetchall()

        stats["checked"] = len(rows)
        try:
            for item_id, name in rows:
                normalized = normalize_product_name(name)
                if not normalized:
                    stats["skipped"] += 1
                    continue
                if not dry_run:
                    conn.execute(
                        "UPDATE items SET normalized_name = ? WHERE id = ?",
                        (normalized, item_id),
                    )
                stats["updated"] += 1

            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        except Exception:
            conn.rollback()
            stats["errors"] += 1
            raise

    return stats


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stats = backfill_normalized_names(dry_run=args.dry_run)
    print(f"Всего проверено: {stats['checked']}")
    print(f"Обновлено: {stats['updated']}")
    print(f"Пропущено: {stats['skipped']}")
    print(f"Ошибок: {stats['errors']}")


if __name__ == "__main__":
    main()
