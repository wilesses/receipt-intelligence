import argparse
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

import app.db as db
from app.product_normalizer import normalize_product_name


TARGET_FIELD = "normalized_name"


def create_backup(backup_dir: Path | None = None) -> Path:
    return db.backup_database("normalized_backfill", backup_dir)


def _row_after(row, normalized: str) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "canonical_name": row["canonical_name"],
        "before": row["normalized_name"],
        "after": normalized,
    }


def _read_only_connection():
    path = Path(db.DB_PATH).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def plan_normalized_name_backfill(example_limit: int = 20) -> dict:
    stats = Counter()
    examples = []
    unresolved = []

    with closing(_read_only_connection()) as conn:
        rows = conn.execute("""
            SELECT id, name, canonical_name, normalized_name
            FROM items
            ORDER BY id
        """).fetchall()

    stats["checked"] = len(rows)
    for row in rows:
        current = (row["normalized_name"] or "").strip()
        if current:
            stats["already_filled"] += 1
            continue

        normalized = normalize_product_name(row["name"])
        if not normalized:
            stats["unresolved"] += 1
            if len(unresolved) < example_limit:
                unresolved.append({"id": row["id"], "name": row["name"]})
            continue

        stats["to_update"] += 1
        if len(examples) < example_limit:
            examples.append(_row_after(row, normalized))

    return {
        "target_fields": [TARGET_FIELD],
        "stats": dict(stats),
        "examples": examples,
        "unresolved_examples": unresolved,
    }


def backfill_normalized_names(*, apply: bool = False, backup_dir: Path | None = None, example_limit: int = 20) -> dict:
    plan = plan_normalized_name_backfill(example_limit=example_limit)
    stats = Counter(plan["stats"])
    stats["errors"] = 0
    backup_path = None

    if not apply:
        plan["stats"] = dict(stats)
        plan["dry_run"] = True
        plan["backup_path"] = None
        return plan

    with db.get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        backup_path = create_backup(backup_dir)
        rows = conn.execute("""
            SELECT id, name
            FROM items
            WHERE normalized_name IS NULL OR TRIM(normalized_name) = ''
            ORDER BY id
        """).fetchall()

        try:
            for item_id, name in rows:
                normalized = normalize_product_name(name)
                if not normalized:
                    continue
                conn.execute(
                    "UPDATE items SET normalized_name = ? WHERE id = ?",
                    (normalized, item_id),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            stats["errors"] += 1
            raise

    plan["stats"] = dict(stats)
    plan["dry_run"] = False
    plan["backup_path"] = str(backup_path)
    return plan


def print_report(result: dict) -> None:
    stats = result["stats"]
    mode = "dry-run" if result["dry_run"] else "apply"
    print(f"Mode: {mode}")
    print(f"Target fields: {', '.join(result['target_fields'])}")
    print(f"Rows checked: {stats.get('checked', 0)}")
    print(f"Rows to update: {stats.get('to_update', 0)}")
    print(f"Already filled: {stats.get('already_filled', 0)}")
    print(f"Unresolved: {stats.get('unresolved', 0)}")
    if result.get("backup_path"):
        print(f"Backup: {result['backup_path']}")

    print("Examples:")
    for item in result["examples"]:
        print(f"  #{item['id']}: {item['before']!r} -> {item['after']!r} ({item['name']})")

    if result["unresolved_examples"]:
        print("Unresolved examples:")
        for item in result["unresolved_examples"]:
            print(f"  #{item['id']}: {item['name']!r}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    mode.add_argument("--dry-run", action="store_true", help="Accepted for compatibility; dry-run is default.")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--examples", type=int, default=20)
    args = parser.parse_args()

    result = backfill_normalized_names(
        apply=args.apply,
        backup_dir=args.backup_dir,
        example_limit=args.examples,
    )
    print_report(result)


if __name__ == "__main__":
    main()
