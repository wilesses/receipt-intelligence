import argparse
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

import app.db as db
from app.price_model import derive_price_data


TARGET_FIELDS = [
    "line_total",
    "unit_price",
    "quantity_unit",
    "package_size",
    "package_unit",
    "normalized_unit_price",
    "normalized_price_unit",
    "price_parse_source",
    "price_parse_confidence",
]
VALUE_FIELDS = TARGET_FIELDS[:-2]
UNIT_FIELDS = {"quantity_unit", "package_unit", "normalized_price_unit"}
SAFE_APPLY_SOURCES = {"package_name", "weighted_inference"}
MANUAL_REVIEW_ITEM_IDS = {3544, 3578, 3579, 3581}
HIGH_CONFIDENCE_CONFLICT_WARNINGS = {
    "ambiguous_package_size",
    "invalid_package_size",
    "multipack_unresolved",
    "normalized_unit_price_suspicious",
    "parser_contamination",
    "service_line",
}


def create_backup(backup_dir: Path | None = None) -> Path:
    return db.backup_database("price_backfill", backup_dir)


def _normalize_sources(sources) -> set[str] | None:
    if sources is None:
        return None
    if isinstance(sources, str):
        selected = {source.strip() for source in sources.split(",") if source.strip()}
    else:
        selected = {str(source).strip() for source in sources if str(source).strip()}
    unknown = selected - SAFE_APPLY_SOURCES
    if unknown:
        raise ValueError(
            f"Unknown source(s): {', '.join(sorted(unknown))}. "
            f"Allowed sources: {', '.join(sorted(SAFE_APPLY_SOURCES))}"
        )
    if not selected:
        raise ValueError("--sources must contain at least one allowed source")
    return selected


def _candidate_values(data) -> dict:
    return {
        "line_total": data.line_total,
        "unit_price": data.unit_price,
        "quantity_unit": data.quantity_unit,
        "package_size": data.package_size,
        "package_unit": data.package_unit,
        "normalized_unit_price": data.normalized_unit_price,
        "normalized_price_unit": data.normalized_price_unit,
        "price_parse_source": data.source,
        "price_parse_confidence": data.confidence,
    }


def _is_missing(field: str, value) -> bool:
    return value is None or value == "" or (field in UNIT_FIELDS and value == "unknown")


def _is_informative(field: str, value) -> bool:
    return not _is_missing(field, value)


def _merge_price_fields(row, data) -> tuple[dict, list[str]]:
    candidate = _candidate_values(data)
    merged = {field: row[field] for field in TARGET_FIELDS}
    changed = []

    existing_confidence = row["price_parse_confidence"]
    if data.source == "service_line" and (existing_confidence is None or existing_confidence < 0.90):
        corrections = {
            "quantity_unit": "unknown",
            "normalized_unit_price": None,
            "normalized_price_unit": "unknown",
            "price_parse_source": "service_line",
            "price_parse_confidence": None,
        }
        for field, value in corrections.items():
            if merged[field] != value:
                merged[field] = value
                changed.append(field)
        return merged, changed

    for field in VALUE_FIELDS:
        new_value = candidate[field]
        if new_value is None or new_value == "":
            continue
        if _is_missing(field, merged[field]) and merged[field] != new_value:
            merged[field] = new_value
            changed.append(field)

    compatible = all(
        not _is_informative(field, candidate[field])
        or _is_missing(field, row[field])
        or row[field] == candidate[field]
        for field in VALUE_FIELDS
    )
    candidate_confidence = candidate["price_parse_confidence"]
    stronger_candidate = (
        changed
        and candidate_confidence is not None
        and (existing_confidence is None or candidate_confidence > existing_confidence)
    )
    if stronger_candidate:
        for field in ("price_parse_source", "price_parse_confidence"):
            if merged[field] != candidate[field]:
                merged[field] = candidate[field]
                changed.append(field)
    elif changed or compatible:
        for field in ("price_parse_source", "price_parse_confidence"):
            new_value = candidate[field]
            if _is_missing(field, merged[field]) and new_value not in (None, ""):
                merged[field] = new_value
                changed.append(field)
    return merged, changed


def _derive_row(row):
    return derive_price_data(
        name=row["name"] or "",
        normalized_name=row["normalized_name"],
        quantity=row["quantity"],
        line_total=row["price"],
        unit_price=row["unit_price"],
        quantity_unit=row["quantity_unit"],
        package_size=row["package_size"],
        package_unit=row["package_unit"],
        source=row["price_parse_source"] or "legacy_backfill",
    )


def _before_after(row, data, merged=None, changed_fields=None) -> dict:
    merged = merged or _candidate_values(data)
    return {
        "id": row["id"],
        "name": row["name"],
        "quantity": row["quantity"],
        "price": row["price"],
        "before": {field: row[field] for field in TARGET_FIELDS},
        "after": merged,
        "changed_fields": changed_fields or [],
        "warnings": data.warnings,
    }


def _high_confidence_conflict(row, data) -> dict | None:
    confidence = row["price_parse_confidence"]
    reasons = sorted(HIGH_CONFIDENCE_CONFLICT_WARNINGS.intersection(data.warnings))
    if row["id"] in MANUAL_REVIEW_ITEM_IDS:
        reasons = sorted(set(reasons) | {"manual_review_item"})
    if confidence is None or confidence < 0.90 or not reasons:
        return None
    if "manual_review_item" in reasons:
        verdict, action = "manual_review", "preserve"
    elif "service_line" in reasons:
        verdict, action = "service_line", "clear later"
    elif "parser_contamination" in reasons:
        verdict, action = "parser_contamination", "manual review"
    elif "multipack_unresolved" in reasons:
        verdict, action = "multipack", "manual review"
    elif {"ambiguous_package_size", "invalid_package_size"}.intersection(reasons):
        verdict, action = "malformed_or_ambiguous_package", "manual review"
    else:
        verdict, action = "suspicious", "manual review"
    return {
        "id": row["id"],
        "name": row["name"],
        "quantity": row["quantity"],
        "price": row["price"],
        "before": {field: row[field] for field in TARGET_FIELDS},
        "verdict": verdict,
        "reasons": reasons,
        "recommended_action": action,
    }


def _read_only_connection():
    path = Path(db.DB_PATH).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Database not found: {path}")
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def plan_price_data_backfill(example_limit: int = 20, sources=None) -> dict:
    selected_sources = _normalize_sources(sources)
    stats = Counter()
    confidence_distribution = Counter()
    source_distribution = Counter()
    unit_distribution = Counter()
    examples = []
    suspicious_examples = []
    high_confidence_conflicts = []
    excluded_examples = []
    field_update_counts = Counter()
    excluded_source_distribution = Counter()

    with closing(_read_only_connection()) as conn:
        rows = conn.execute("""
            SELECT id, name, normalized_name, quantity, price,
                   line_total, unit_price, quantity_unit, package_size, package_unit,
                   normalized_unit_price, normalized_price_unit, price_parse_source,
                   price_parse_confidence, category, category_source, canonical_name
            FROM items
            ORDER BY id
        """).fetchall()

    stats["checked"] = len(rows)
    for row in rows:
        data = _derive_row(row)
        merged, changed_fields = _merge_price_fields(row, data)
        conflict = _high_confidence_conflict(row, data)
        if conflict:
            high_confidence_conflicts.append(conflict)
        selected = selected_sources is None or data.source in selected_sources
        eligible = selected and conflict is None
        stats["warnings"] += len(data.warnings)
        normalized_unit = merged["normalized_price_unit"] or "unknown"
        confidence = merged["price_parse_confidence"]
        confidence_bucket = "NULL" if confidence is None else f"{float(confidence):.2f}"
        final_source = merged["price_parse_source"] or "NULL"

        if normalized_unit == "unknown":
            stats["unresolved"] += 1
        else:
            stats["enriched"] += 1
        if final_source == "parser" and confidence == 0.95:
            stats["parser_confirmed"] += 1
        if final_source == "package_name":
            stats["package_derived"] += 1
        if final_source == "inferred_piece":
            stats["inferred_piece"] += 1
        if data.source == "service_line":
            stats["service_lines"] += 1
        if merged["quantity_unit"] in {"kg", "g", "l", "ml"}:
            stats["weighted_items"] += 1
        if "multipack_unresolved" in data.warnings:
            stats["multipack"] += 1
        if data.source == "rejected":
            stats["rejected_suspicious"] += 1

        if selected_sources is not None and not eligible:
            if changed_fields or conflict:
                reason = "high_confidence_conflict" if conflict else data.source
                excluded_source_distribution[reason] += 1
                if len(excluded_examples) < example_limit:
                    excluded_examples.append(_before_after(row, data, merged, changed_fields))
            if data.source == "inferred_piece":
                stats["excluded_inferred_piece"] += 1
            continue

        if selected_sources is None or changed_fields:
            confidence_distribution[confidence_bucket] += 1
            source_distribution[final_source] += 1
            unit_distribution[normalized_unit] += 1
        if changed_fields:
            stats["to_update"] += 1
            field_update_counts.update(changed_fields)
            if len(examples) < example_limit:
                examples.append(_before_after(row, data, merged, changed_fields))
            if data.warnings and len(suspicious_examples) < example_limit:
                suspicious_examples.append(_before_after(row, data, merged, changed_fields))
        else:
            stats["skipped_existing_quality"] += 1

    stats["excluded_conflicts"] = len(high_confidence_conflicts)
    return {
        "target_fields": TARGET_FIELDS,
        "selected_sources": sorted(selected_sources) if selected_sources else None,
        "stats": dict(stats),
        "confidence_distribution": dict(sorted(confidence_distribution.items())),
        "source_distribution": dict(sorted(source_distribution.items())),
        "unit_distribution": dict(sorted(unit_distribution.items())),
        "examples": examples,
        "suspicious_examples": suspicious_examples,
        "high_confidence_conflicts": high_confidence_conflicts,
        "excluded_examples": excluded_examples,
        "excluded_source_distribution": dict(sorted(excluded_source_distribution.items())),
        "field_update_counts": dict(sorted(field_update_counts.items())),
    }


def backfill_price_data(
    *, apply: bool = False, sources=None, backup_dir: Path | None = None, example_limit: int = 20
) -> dict:
    selected_sources = _normalize_sources(sources)
    if apply and selected_sources is None:
        raise ValueError("--apply requires an explicit --sources list")
    plan = plan_price_data_backfill(example_limit=example_limit, sources=selected_sources)
    stats = Counter(plan["stats"])
    stats["errors"] = 0
    backup_path = None

    if not apply:
        plan["stats"] = dict(stats)
        plan["dry_run"] = True
        plan["backup_path"] = None
        return plan

    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        backup_path = create_backup(backup_dir)
        rows = conn.execute("""
            SELECT id, name, normalized_name, quantity, price,
                   line_total, unit_price, quantity_unit, package_size, package_unit,
                   normalized_unit_price, normalized_price_unit, price_parse_source,
                   price_parse_confidence
            FROM items
            ORDER BY id
        """).fetchall()
        try:
            for row in rows:
                data = _derive_row(row)
                if data.source not in selected_sources or _high_confidence_conflict(row, data):
                    continue
                merged, changed_fields = _merge_price_fields(row, data)
                if not changed_fields:
                    continue
                assignments = ", ".join(f"{field} = ?" for field in changed_fields)
                values = [merged[field] for field in changed_fields]
                conn.execute(f"UPDATE items SET {assignments} WHERE id = ?", (*values, row["id"]))

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
    if result.get("selected_sources"):
        print(f"Selected sources: {', '.join(result['selected_sources'])}")
    print(f"Rows checked: {stats.get('checked', 0)}")
    print(f"Rows to update: {stats.get('to_update', 0)}")
    print(f"Enriched: {stats.get('enriched', 0)}")
    print(f"Unresolved: {stats.get('unresolved', 0)}")
    print(f"Skipped existing quality: {stats.get('skipped_existing_quality', 0)}")
    print(f"Warnings: {stats.get('warnings', 0)}")
    print(f"Parser confirmed: {stats.get('parser_confirmed', 0)}")
    print(f"Package derived: {stats.get('package_derived', 0)}")
    print(f"Inferred piece: {stats.get('inferred_piece', 0)}")
    print(f"Service/non-product: {stats.get('service_lines', 0)}")
    print(f"Weighted items: {stats.get('weighted_items', 0)}")
    print(f"Multipack: {stats.get('multipack', 0)}")
    print(f"Rejected/suspicious: {stats.get('rejected_suspicious', 0)}")
    if result.get("backup_path"):
        print(f"Backup: {result['backup_path']}")
    print(f"Confidence distribution: {result['confidence_distribution']}")
    print(f"Source distribution: {result['source_distribution']}")
    print(f"Unit distribution: {result['unit_distribution']}")
    print(f"Field updates: {result.get('field_update_counts', {})}")
    print(f"Excluded sources: {result.get('excluded_source_distribution', {})}")

    print("Examples:")
    for item in result["examples"]:
        after = item["after"]
        print(
            f"  #{item['id']}: {item['name']} | "
            f"unit={after['quantity_unit']} normalized={after['normalized_unit_price']} "
            f"{after['normalized_price_unit']} confidence={after['price_parse_confidence']}"
        )

    if result["suspicious_examples"]:
        print("Suspicious examples:")
        for item in result["suspicious_examples"]:
            print(f"  #{item['id']}: {item['name']} warnings={','.join(item['warnings'])}")

    if result["high_confidence_conflicts"]:
        print("High-confidence conflicts:")
        for item in result["high_confidence_conflicts"]:
            print(
                f"  #{item['id']}: {item['name']} verdict={item['verdict']} "
                f"reasons={','.join(item['reasons'])} action={item['recommended_action']}"
            )

    if result.get("excluded_examples"):
        print("Excluded examples:")
        for item in result["excluded_examples"]:
            print(f"  #{item['id']}: {item['name']} warnings={','.join(item['warnings'])}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    mode.add_argument("--dry-run", action="store_true", help="Accepted for compatibility; dry-run is default.")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--examples", type=int, default=20)
    parser.add_argument("--sources", help="Comma-separated sources allowed for this run.")
    args = parser.parse_args()
    try:
        result = backfill_price_data(
            apply=args.apply,
            sources=args.sources,
            backup_dir=args.backup_dir,
            example_limit=args.examples,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print_report(result)


if __name__ == "__main__":
    main()
