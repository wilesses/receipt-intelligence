import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from app.category_keywords import (
    UNRESOLVED_CATEGORY,
    category_for_reporting,
    categorize_from_name,
    normalize_category_name,
)
from app.config import DB_PATH
from app.product_normalizer import normalize_product_name


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _summarize(records: list[dict]) -> dict:
    exact = sum(record["persisted"] == record["predicted"] for record in records)
    fallback = sum(record["predicted"] == UNRESOLVED_CATEGORY for record in records)
    identities = defaultdict(list)
    confusion = Counter()
    pair_examples = defaultdict(list)
    samples = defaultdict(list)

    for record in records:
        identities[record["effective_identity"]].append(record)
        pair = f'{record["persisted"]} -> {record["predicted"]}'
        confusion[pair] += 1
        if len(pair_examples[pair]) < 3:
            pair_examples[pair].append(record["name"])
        if len(samples[record["predicted"]]) < 3:
            samples[record["predicted"]].append({
                "name": record["name"],
                "persisted": record["persisted"],
                "match": record["persisted"] == record["predicted"],
            })

    exact_identities = sum(
        all(record["persisted"] == record["predicted"] for record in group)
        for group in identities.values()
    )
    mismatches = [
        {"pair": pair, "count": count, "examples": pair_examples[pair]}
        for pair, count in confusion.most_common()
        if pair.split(" -> ", 1)[0] != pair.split(" -> ", 1)[1]
    ]

    return {
        "rows": len(records),
        "exact_matches": exact,
        "exact_rate": _rate(exact, len(records)),
        "fallback_count": fallback,
        "fallback_rate": _rate(fallback, len(records)),
        "effective_identities": len(identities),
        "exact_identities": exact_identities,
        "exact_identity_rate": _rate(exact_identities, len(identities)),
        "confusion": dict(sorted(confusion.items())),
        "mismatches": mismatches,
        "samples_by_prediction": dict(sorted(samples.items())),
    }


def evaluate_database(db_path: str | Path = DB_PATH) -> dict:
    path = Path(db_path).resolve()
    uri = f"{path.as_uri()}?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        rules = {
            product_key: normalize_category_name(category)
            for product_key, category in conn.execute(
                "SELECT product_key, category FROM product_category_rules"
            )
        }
        rows = conn.execute(
            """
            SELECT id, name, normalized_name, canonical_name, category
            FROM items
            ORDER BY id
            """
        ).fetchall()

    records = []
    for item_id, name, normalized_name, canonical_name, category in rows:
        raw_key = (normalized_name or "").strip() or normalize_product_name(name or "")
        rule_category = rules.get(raw_key)
        records.append({
            "item_id": item_id,
            "name": name or "",
            "effective_identity": canonical_name.strip() if canonical_name and canonical_name.strip() else name or "",
            "persisted": category_for_reporting(category),
            "predicted": categorize_from_name(name or ""),
            "rule_covered": rule_category is not None,
            "rule_category": rule_category,
        })

    covered = [record for record in records if record["rule_covered"]]
    rule_free = [record for record in records if not record["rule_covered"]]
    return {
        "database": str(path),
        "overall": _summarize(records),
        "rule_covered": _summarize(covered),
        "rule_free": _summarize(rule_free),
        "rule_override_rows": sum(
            record["rule_category"] != record["predicted"] for record in covered
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Category Classifier v2 shadow evaluation")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    print(json.dumps(evaluate_database(args.db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
