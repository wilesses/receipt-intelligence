import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.config import DB_PATH
from app.price_model import derive_price_data


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "docs" / "audits" / "2026-08-25-price-arithmetic-mismatch-safe-candidates.csv"
ALLOWLIST = (3577, 3615, 3670, 3671, 3674, 3675)
EXPECTED_MISMATCHES_BEFORE = (3575, 3577, 3613, 3614, 3615, 3668, 3670, 3671, 3674, 3675)
EXPECTED_MISMATCHES_AFTER = (3575, 3613, 3614, 3668)
PRICE_MODEL_FIELDS = (
    "quantity",
    "line_total",
    "unit_price",
    "quantity_unit",
    "package_size",
    "package_unit",
    "normalized_unit_price",
    "normalized_price_unit",
    "price_parse_source",
    "price_parse_confidence",
)
DERIVED_FIELDS = PRICE_MODEL_FIELDS[2:]
EXPECTED_BEFORE = {
    3577: (360, "Tualetes papirs Zewa Everyday 32 rulli", 1.0, 8.99, 8.99, 19.99, "piece", None, "unknown", 8.99, "eur_per_piece", "parser", 0.70),
    3615: (365, "Rieksti Adazu ar kréjuma,sipola garsu 140g", 1.0, 1.99, 1.99, 2.99, "piece", 140.0, "g", 14.2143, "eur_per_kg", "parser", 0.95),
    3670: (371, "Gurki isie, kg", 0.448, 0.53, 0.53, 2.39, "kg", None, "unknown", 1.183, "eur_per_kg", "parser", 0.95),
    3671: (371, "Baltmaize Zemnieku sagriezta 500g", 1.0, 0.85, 0.85, 1.25, "piece", 500.0, "g", 1.7, "eur_per_kg", "parser", 0.95),
    3674: (371, "Zala téja LOYD citronu&citronzales 30g", 1.0, 2.09, 2.09, 2.99, "piece", 30.0, "g", 69.6667, "eur_per_kg", "parser", 0.95),
    3675: (371, "Energijas dz. Cult Energy Dragon Power 500ml", 1.0, 0.89, 0.89, 1.55, "piece", 500.0, "ml", 1.78, "eur_per_l", "parser", 0.95),
}
EXPECTED_AFTER = {
    3577: (1.0, 8.99, 8.99, "piece", None, "unknown", 8.99, "eur_per_piece", "parser", 0.95),
    3615: (1.0, 1.99, 1.99, "piece", 140.0, "g", 14.2143, "eur_per_kg", "parser", 0.95),
    3670: (0.448, 0.53, 1.183, "kg", None, "unknown", 1.183, "eur_per_kg", "parser", 0.95),
    3671: (1.0, 0.85, 0.85, "piece", 500.0, "g", 1.7, "eur_per_kg", "parser", 0.95),
    3674: (1.0, 2.09, 2.09, "piece", 30.0, "g", 69.6667, "eur_per_kg", "parser", 0.95),
    3675: (1.0, 0.89, 0.89, "piece", 500.0, "ml", 1.78, "eur_per_l", "parser", 0.95),
}


def _same(actual, expected):
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return Decimal(str(actual)) == Decimal(str(expected))
    return actual == expected


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _connect(path, *, readonly=False):
    if readonly:
        conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _integrity(conn):
    return conn.execute("PRAGMA integrity_check").fetchone()[0]


def _counts(conn):
    return {
        "receipts": conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],
        "items": conn.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "rules": conn.execute("SELECT COUNT(*) FROM product_category_rules").fetchone()[0],
    }


def _mismatches(conn):
    return tuple(row[0] for row in conn.execute("""
        SELECT id FROM items
        WHERE quantity > 0
          AND unit_price IS NOT NULL
          AND ROUND(ABS(quantity * unit_price - COALESCE(line_total, price)), 4) > 0.02
        ORDER BY id
    """))


def _target_rows(conn):
    placeholders = ",".join("?" for _ in ALLOWLIST)
    rows = conn.execute(f"""
        SELECT *, COALESCE(NULLIF(TRIM(canonical_name), ''), name) AS effective_product
        FROM items WHERE id IN ({placeholders}) ORDER BY id
    """, ALLOWLIST).fetchall()
    return {row["id"]: row for row in rows}


def _csv_projection():
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    ids = tuple(int(row["item_id"]) for row in rows)
    if ids != ALLOWLIST:
        raise RuntimeError(f"Authoritative CSV allowlist mismatch: {ids}")
    return {int(row["item_id"]): row for row in rows}


def _derive(row):
    first = derive_price_data(
        name=row["name"],
        normalized_name=row["normalized_name"],
        quantity=row["quantity"],
        line_total=row["line_total"],
        unit_price=row["unit_price"],
        quantity_unit=row["quantity_unit"],
        package_size=row["package_size"],
        package_unit=row["package_unit"],
        source=row["price_parse_source"],
    )
    return derive_price_data(
        name=row["name"],
        normalized_name=row["normalized_name"],
        quantity=first.quantity,
        line_total=first.line_total,
        unit_price=first.unit_price,
        quantity_unit=first.quantity_unit,
        package_size=first.package_size,
        package_unit=first.package_unit,
        source=first.source,
    )


def _projected_values(data):
    return (
        data.quantity,
        data.line_total,
        data.unit_price,
        data.quantity_unit,
        data.package_size,
        data.package_unit,
        data.normalized_unit_price,
        data.normalized_price_unit,
        data.source,
        data.confidence,
    )


def _require_projection(item_id, row, data, csv_row):
    expected = EXPECTED_AFTER[item_id]
    actual = _projected_values(data)
    if not all(_same(a, e) for a, e in zip(actual, expected)) or data.warnings:
        raise RuntimeError(f"#{item_id} derive_price_data projection mismatch: {actual}, warnings={data.warnings}")
    csv_expected = (
        csv_row["projected_quantity"],
        csv_row["projected_price"],
        csv_row["projected_line_total"],
        csv_row["projected_unit_price"],
        csv_row["projected_normalized_price"],
        csv_row["projected_normalized_unit"],
    )
    csv_actual = (data.quantity, row["price"], data.line_total, data.unit_price, data.normalized_unit_price, data.normalized_price_unit)
    if not all(_same(a, float(e) if i < 5 else e) for i, (a, e) in enumerate(zip(csv_actual, csv_expected))):
        raise RuntimeError(f"#{item_id} projection differs from authoritative CSV")


def _preflight(conn, *, allow_applied=False):
    csv_rows = _csv_projection()
    rows = _target_rows(conn)
    if tuple(rows) != ALLOWLIST:
        raise RuntimeError(f"Target row set mismatch: {tuple(rows)}")
    states = []
    projections = {}
    for item_id, row in rows.items():
        expected = EXPECTED_BEFORE[item_id]
        actual = (
            row["receipt_id"], row["effective_product"], row["quantity"], row["price"], row["line_total"],
            row["unit_price"], row["quantity_unit"], row["package_size"], row["package_unit"],
            row["normalized_unit_price"], row["normalized_price_unit"], row["price_parse_source"],
            row["price_parse_confidence"],
        )
        before = all(_same(a, e) for a, e in zip(actual, expected))
        applied_expected = (expected[0], expected[1], row["price"], *EXPECTED_AFTER[item_id])
        applied_actual = (row["receipt_id"], row["effective_product"], row["price"], *[row[field] for field in PRICE_MODEL_FIELDS])
        applied = all(_same(a, e) for a, e in zip(applied_actual, applied_expected))
        states.append("before" if before else "applied" if applied else "stale")
        if before:
            data = _derive(row)
            _require_projection(item_id, row, data, csv_rows[item_id])
            projections[item_id] = data
    if all(state == "applied" for state in states) and allow_applied:
        return rows, projections, "already_applied"
    if not all(state == "before" for state in states):
        raise RuntimeError(f"Audited before-state mismatch: {dict(zip(ALLOWLIST, states))}")
    if _mismatches(conn) != EXPECTED_MISMATCHES_BEFORE:
        raise RuntimeError(f"Arithmetic mismatch set changed: {_mismatches(conn)}")
    return rows, projections, "ready"


def _snapshot(conn, table):
    columns = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
    rows = {row[0]: tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1")}
    return columns, rows


def _verify_against_backup(db_path, backup_path):
    with _connect(db_path, readonly=True) as after, _connect(backup_path, readonly=True) as before:
        if _integrity(after) != "ok":
            raise RuntimeError("Production integrity_check failed after commit")
        if _counts(after) != _counts(before):
            raise RuntimeError("Table counts changed")
        for table in ("receipts", "product_category_rules"):
            if _snapshot(after, table) != _snapshot(before, table):
                raise RuntimeError(f"Unexpected changes in {table}")
        columns, before_items = _snapshot(before, "items")
        after_columns, after_items = _snapshot(after, "items")
        if columns != after_columns or before_items.keys() != after_items.keys():
            raise RuntimeError("Items schema or row set changed")
        changed_ids = tuple(item_id for item_id in before_items if before_items[item_id] != after_items[item_id])
        if changed_ids != ALLOWLIST:
            raise RuntimeError(f"Out-of-allowlist item changes: {changed_ids}")
        allowed_indexes = {columns.index(field) for field in DERIVED_FIELDS}
        changes = {}
        for item_id in ALLOWLIST:
            changed_fields = {
                column: (before_items[item_id][index], after_items[item_id][index])
                for index, column in enumerate(columns)
                if before_items[item_id][index] != after_items[item_id][index]
            }
            if not changed_fields or any(columns.index(field) not in allowed_indexes for field in changed_fields):
                raise RuntimeError(f"#{item_id} changed forbidden fields: {changed_fields}")
            changes[item_id] = changed_fields
        mismatches = _mismatches(after)
        if mismatches != EXPECTED_MISMATCHES_AFTER:
            raise RuntimeError(f"Post-write mismatch set differs: {mismatches}")
        return {
            "integrity": "ok",
            "counts": _counts(after),
            "changed_ids": changed_ids,
            "changes": changes,
            "mismatches": mismatches,
        }


def run(*, apply=False):
    db_path = Path(DB_PATH).resolve()
    with _connect(db_path, readonly=True) as conn:
        integrity = _integrity(conn)
        if integrity != "ok":
            raise RuntimeError(f"Production integrity_check failed: {integrity}")
        counts = _counts(conn)
        rows, projections, status = _preflight(conn, allow_applied=True)
        preflight = {
            "status": status,
            "sha256": _sha256(db_path),
            "integrity": integrity,
            "counts": counts,
            "mismatches": _mismatches(conn),
            "targets": {
                item_id: {field: rows[item_id][field] for field in ("receipt_id", "name", "quantity", "price", "line_total", *DERIVED_FIELDS)}
                for item_id in ALLOWLIST
            },
        }
    if status == "already_applied":
        return {"mode": "noop", "preflight": preflight}
    if not apply:
        return {"mode": "dry-run", "preflight": preflight}

    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"{db_path.stem}_before_price_arithmetic_safe_repair_{timestamp}{db_path.suffix}"
    with _connect(db_path, readonly=True) as source, _connect(backup_path) as target:
        source.backup(target)
        backup_integrity = _integrity(target)
        if backup_integrity != "ok":
            raise RuntimeError(f"Backup integrity_check failed: {backup_integrity}")
    backup = {
        "path": str(backup_path),
        "sha256": _sha256(backup_path),
        "integrity": backup_integrity,
        "counts": counts,
    }

    with _connect(db_path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            locked_rows, locked_projections, locked_status = _preflight(conn)
            if locked_status != "ready":
                raise RuntimeError(f"Unexpected locked preflight status: {locked_status}")
            for item_id in ALLOWLIST:
                row = locked_rows[item_id]
                data = locked_projections[item_id]
                projected = dict(zip(PRICE_MODEL_FIELDS, _projected_values(data)))
                changes = {field: projected[field] for field in DERIVED_FIELDS if not _same(row[field], projected[field])}
                if not changes:
                    raise RuntimeError(f"#{item_id} has no stale derived fields")
                assignments = ", ".join(f"{field} = ?" for field in changes)
                predicates = " AND ".join(f"{field} IS ?" for field in ("id", "receipt_id", "name", "normalized_name", "canonical_name", "category", "category_source", "quantity", "price", "line_total", *DERIVED_FIELDS))
                values = [changes[field] for field in changes]
                before_values = [row[field] for field in ("id", "receipt_id", "name", "normalized_name", "canonical_name", "category", "category_source", "quantity", "price", "line_total", *DERIVED_FIELDS)]
                cursor = conn.execute(f"UPDATE items SET {assignments} WHERE {predicates}", (*values, *before_values))
                if cursor.rowcount != 1:
                    raise RuntimeError(f"#{item_id} optimistic update affected {cursor.rowcount} rows")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    post = _verify_against_backup(db_path, backup_path)
    post["sha256"] = _sha256(db_path)
    return {"mode": "apply", "preflight": preflight, "backup": backup, "post": post}


def main():
    parser = argparse.ArgumentParser(description="Apply the exact six-row audited derived Price Model repair.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), ensure_ascii=False, indent=2, default=list))


if __name__ == "__main__":
    main()
