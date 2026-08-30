import argparse
import json
import sys
from collections import Counter

from app.category_keywords import (
    CANONICAL_CATEGORIES,
    UNRESOLVED_CATEGORY,
    category_for_reporting,
)
from app.category_rules import get_product_key
from app.db import get_connection


def audit_categories() -> dict:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT items.id, items.name, items.normalized_name, items.canonical_name,
                   items.category, items.category_source
            FROM items
        """).fetchall()
        rules = conn.execute("SELECT product_key, category FROM product_category_rules").fetchall()

    category_counts = Counter(row[4] or "" for row in rows)
    source_counts = Counter(row[5] or "" for row in rows)
    canonical = set(CANONICAL_CATEGORIES)
    empty_categories = sum(1 for row in rows if not row[4] or not str(row[4]).strip())
    unknown_categories = sorted({
        category
        for category in category_counts
        if category and category_for_reporting(category) not in canonical
    })

    groups = {}
    rule_keys = {row[0] for row in rules}
    covered_by_rules = 0
    for _, name, normalized_name, canonical_name, category, category_source in rows:
        key = get_product_key(name or "", normalized_name, canonical_name)
        group = groups.setdefault(key, set())
        group.add(category_for_reporting(category))
        if key in rule_keys:
            covered_by_rules += 1

    conflict_groups = sum(1 for categories in groups.values() if len(categories) > 1)

    return {
        "total_items": len(rows),
        "category_counts": dict(category_counts),
        "category_source_counts": dict(source_counts),
        "empty_categories": empty_categories,
        "unknown_categories": unknown_categories,
        "conflict_groups": conflict_groups,
        "other_count": sum(
            count
            for category, count in category_counts.items()
            if category_for_reporting(category) == UNRESOLVED_CATEGORY
        ),
        "manual_rules": len(rule_keys),
        "rows_covered_by_manual_rules": covered_by_rules,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit_categories()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Всего items: {result['total_items']}")
    print("Количество по category:")
    for category, count in sorted(result["category_counts"].items(), key=lambda item: (-item[1], item[0])):
        print(f"  {category or '<пусто>'}: {count}")
    print("Количество по category_source:")
    for source, count in sorted(result["category_source_counts"].items(), key=lambda item: (-item[1], item[0])):
        print(f"  {source or '<пусто>'}: {count}")
    print(f"Пустые категории: {result['empty_categories']}")
    print(f"Неизвестные категории: {', '.join(result['unknown_categories']) or 'нет'}")
    print(f"Группы с конфликтами категорий: {result['conflict_groups']}")
    print(f"Прочее: {result['other_count']}")
    print(f"Manual rules: {result['manual_rules']}")
    print(f"Строк покрыто manual rules: {result['rows_covered_by_manual_rules']}")


if __name__ == "__main__":
    main()
