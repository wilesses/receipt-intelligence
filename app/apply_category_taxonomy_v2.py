import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.category_rules import get_product_key
from app.config import DB_PATH
from app.db import backup_database
from app.product_identity import effective_product_identity_sql


APPROVED_CATEGORIES = (
    "овощи и фрукты",
    "мясо и птица",
    "рыба и морепродукты",
    "молочные продукты и альтернативы",
    "яйца",
    "хлеб и выпечка",
    "бакалея и основные продукты",
    "готовая еда и быстрое приготовление",
    "замороженные продукты",
    "соусы, приправы и консервы",
    "снеки и сладости",
    "безалкогольные напитки",
    "алкоголь",
    "детское",
    "товары для животных",
    "бытовое и личный уход",
    "служебные строки",
    "прочее / требует решения",
)
RECOGNIZED_OPERATIONS = {
    "LABEL_ONLY",
    "CREATE_EXACT_RULE",
    "UPDATE_EXISTING_RULE",
    "MULTI_RULE_EXACT",
}
REQUIRED_COLUMNS = {
    "effective_product",
    "product_key",
    "target_category",
    "current_categories",
    "expected_affected_item_count",
    "expected_rule_operation",
    "before_state_predicates",
    "required_exact_exclusions",
    "protected_item_ids",
    "reason",
    "confidence",
}


class MigrationValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    effective_product: str
    product_key: str
    target_category: str
    current_categories: str
    expected_affected_item_count: int
    expected_rule_operation: str
    predicates: dict
    reason: str


@dataclass(frozen=True)
class ItemChange:
    item_id: int
    effective_product: str
    old_category: str
    new_category: str


@dataclass(frozen=True)
class RuleUpdate:
    product_key: str
    old_category: str
    new_category: str
    old_source: str
    old_updated_at: str


@dataclass(frozen=True)
class RuleInsert:
    product_key: str
    category: str


@dataclass(frozen=True)
class MigrationPlan:
    candidates: tuple[Candidate, ...]
    item_changes: tuple[ItemChange, ...]
    rule_updates: tuple[RuleUpdate, ...]
    rule_inserts: tuple[RuleInsert, ...]
    rule_unchanged: tuple[str, ...]
    source_target_counts: tuple[tuple[str, str, int], ...]
    operation_counts: tuple[tuple[str, int], ...]

    @property
    def identity_count(self):
        return len(self.candidates)

    def summary(self):
        return {
            "identities": self.identity_count,
            "item_rows_changed": len(self.item_changes),
            "rules_updated": len(self.rule_updates),
            "rules_inserted": len(self.rule_inserts),
            "rules_unchanged": len(self.rule_unchanged),
            "operation_counts": dict(self.operation_counts),
            "source_target_counts": [
                {"source": source, "target": target, "rows": count}
                for source, target, count in self.source_target_counts
            ],
        }


@dataclass(frozen=True)
class DiffSummary:
    changed_item_ids: tuple[int, ...]
    changed_item_fields: tuple[str, ...]
    updated_rule_keys: tuple[str, ...]
    inserted_rule_keys: tuple[str, ...]
    changed_rule_fields: tuple[str, ...]


@dataclass(frozen=True)
class DatabaseSnapshot:
    path: str
    sha256: str
    integrity: str
    receipts: int
    items: int
    rules: int
    effective_identities: int
    total_spend: float
    raw_categories: tuple[tuple[str, int], ...]


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _read_only_connection(path, immutable=False):
    suffix = "?mode=ro&immutable=1" if immutable else "?mode=ro"
    return sqlite3.connect(Path(path).resolve().as_uri() + suffix, uri=True)


def load_manifest(path):
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise MigrationValidationError(f"Manifest columns missing: {sorted(missing)}")
        rows = list(reader)

    candidates = []
    seen_identities = set()
    for line_number, row in enumerate(rows, start=2):
        effective_product = row["effective_product"]
        if not effective_product or effective_product in seen_identities:
            raise MigrationValidationError(
                f"Manifest identity missing or duplicated at line {line_number}: {effective_product!r}"
            )
        seen_identities.add(effective_product)
        if row["confidence"] != "HIGH":
            raise MigrationValidationError(f"Non-HIGH candidate: {effective_product}")
        if row["target_category"] not in APPROVED_CATEGORIES:
            raise MigrationValidationError(f"Unapproved target for {effective_product}")
        if row["expected_rule_operation"] not in RECOGNIZED_OPERATIONS:
            raise MigrationValidationError(f"Unknown operation for {effective_product}")
        if row["required_exact_exclusions"].strip() or row["protected_item_ids"].strip():
            raise MigrationValidationError(f"SAFE row has exclusions/protected IDs: {effective_product}")
        try:
            predicates = json.loads(row["before_state_predicates"])
            affected_count = int(row["expected_affected_item_count"])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise MigrationValidationError(
                f"Invalid manifest predicate at line {line_number}: {effective_product}"
            ) from exc
        candidates.append(
            Candidate(
                effective_product=effective_product,
                product_key=row["product_key"],
                target_category=row["target_category"],
                current_categories=row["current_categories"],
                expected_affected_item_count=affected_count,
                expected_rule_operation=row["expected_rule_operation"],
                predicates=predicates,
                reason=row["reason"],
            )
        )
    return tuple(candidates)


def _category_counts_text(items):
    counts = Counter(item[4] for item in items)
    return "|".join(f"{category}:{counts[category]}" for category in sorted(counts))


def _exception_ids(items):
    counts = Counter(item[4] for item in items)
    dominant = sorted(counts, key=lambda category: (-counts[category], category))[0]
    return sorted(item[0] for item in items if item[4] != dominant)


def _rule_text(rule):
    return None if rule is None else f"{rule[1]}|{rule[2]}"


def _validate_candidate_state(candidate, identity_items, key_items, key_identities, rules):
    predicates = candidate.predicates
    if not identity_items:
        raise MigrationValidationError(f"Identity missing: {candidate.effective_product}")

    actual_key = {item[6] for item in identity_items}
    raw_alias_keys = sorted({item[7] for item in identity_items})
    exceptions = _exception_ids(identity_items)
    actual = {
        "current_categories": _category_counts_text(identity_items),
        "effective_product": candidate.effective_product,
        "existing_rule": _rule_text(rules.get(candidate.product_key)),
        "identity_row_count": len(identity_items),
        "item_exception_count": len(exceptions),
        "item_exception_ids": exceptions,
        "product_key": candidate.product_key,
        "raw_alias_keys": raw_alias_keys,
        "rule_scope_rows": len(key_items.get(candidate.product_key, ())),
        "shared_product_key_identity_count": len(key_identities.get(candidate.product_key, ())),
    }
    if actual_key != {candidate.product_key}:
        raise MigrationValidationError(
            f"Product key mismatch for {candidate.effective_product}: {sorted(actual_key)}"
        )
    if candidate.current_categories != actual["current_categories"]:
        raise MigrationValidationError(
            f"Current categories drift for {candidate.effective_product}: "
            f"{candidate.current_categories!r} != {actual['current_categories']!r}"
        )
    if candidate.expected_affected_item_count != actual["rule_scope_rows"]:
        raise MigrationValidationError(
            f"Rule scope drift for {candidate.effective_product}: "
            f"{candidate.expected_affected_item_count} != {actual['rule_scope_rows']}"
        )
    for key, expected in predicates.items():
        if key not in actual:
            raise MigrationValidationError(
                f"Unsupported before-state predicate {key!r} for {candidate.effective_product}"
            )
        if actual[key] != expected:
            raise MigrationValidationError(
                f"Before-state drift for {candidate.effective_product}.{key}: "
                f"{expected!r} != {actual[key]!r}"
            )


def build_migration_plan(conn, candidates):
    item_rows = conn.execute(
        """
        SELECT id, name, normalized_name, canonical_name, category, category_source
        FROM items
        ORDER BY id
        """
    ).fetchall()
    rule_rows = conn.execute(
        """
        SELECT product_key, category, source, created_at, updated_at
        FROM product_category_rules
        ORDER BY product_key
        """
    ).fetchall()
    rules = {row[0]: row for row in rule_rows}
    identity_items = defaultdict(list)
    key_items = defaultdict(list)
    key_identities = defaultdict(set)
    for item_id, name, normalized_name, canonical_name, category, category_source in item_rows:
        effective = canonical_name if canonical_name and canonical_name.strip() else name
        product_key = get_product_key(name or "", normalized_name, canonical_name)
        raw_alias_key = get_product_key(name or "", normalized_name, None)
        state = (
            item_id,
            name,
            normalized_name,
            canonical_name,
            category,
            category_source,
            product_key,
            raw_alias_key,
        )
        identity_items[effective].append(state)
        key_items[product_key].append(state)
        key_identities[product_key].add(effective)

    item_changes = []
    source_target_counts = Counter()
    target_by_rule_key = {}
    desired_rule_keys = set()
    for candidate in candidates:
        scoped_items = identity_items.get(candidate.effective_product, ())
        _validate_candidate_state(
            candidate,
            scoped_items,
            key_items,
            key_identities,
            rules,
        )
        for item in scoped_items:
            if item[4] == candidate.target_category:
                raise MigrationValidationError(
                    f"SAFE row already has target category: {candidate.effective_product}"
                )
            item_changes.append(
                ItemChange(item[0], candidate.effective_product, item[4], candidate.target_category)
            )
            source_target_counts[(item[4], candidate.target_category)] += 1

        operation = candidate.expected_rule_operation
        if operation == "LABEL_ONLY":
            rule_keys = [candidate.product_key] if candidate.product_key in rules else []
        elif operation in {"CREATE_EXACT_RULE", "UPDATE_EXISTING_RULE"}:
            rule_keys = [candidate.product_key]
        else:
            rule_keys = sorted(
                {candidate.product_key, *candidate.predicates["raw_alias_keys"]}
            )
        for rule_key in rule_keys:
            previous_target = target_by_rule_key.setdefault(rule_key, candidate.target_category)
            if previous_target != candidate.target_category:
                raise MigrationValidationError(
                    f"Rule key has mixed target semantics: {rule_key}"
                )
            desired_rule_keys.add(rule_key)

    item_ids = [change.item_id for change in item_changes]
    if len(item_ids) != len(set(item_ids)):
        raise MigrationValidationError("Manifest item scopes overlap")

    rule_updates = []
    rule_inserts = []
    rule_unchanged = []
    for product_key in sorted(desired_rule_keys):
        target = target_by_rule_key[product_key]
        current = rules.get(product_key)
        if current is None:
            rule_inserts.append(RuleInsert(product_key, target))
        elif current[1] == target:
            rule_unchanged.append(product_key)
        else:
            rule_updates.append(
                RuleUpdate(product_key, current[1], target, current[2], current[4])
            )

    operation_counts = Counter(candidate.expected_rule_operation for candidate in candidates)
    return MigrationPlan(
        candidates=tuple(candidates),
        item_changes=tuple(sorted(item_changes, key=lambda change: change.item_id)),
        rule_updates=tuple(rule_updates),
        rule_inserts=tuple(rule_inserts),
        rule_unchanged=tuple(rule_unchanged),
        source_target_counts=tuple(
            (source, target, count)
            for (source, target), count in sorted(source_target_counts.items())
        ),
        operation_counts=tuple(sorted(operation_counts.items())),
    )


def apply_migration_plan(conn, plan):
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for change in plan.item_changes:
            cursor = conn.execute(
                """
                UPDATE items
                SET category = ?
                WHERE id = ? AND category = ?
                """,
                (change.new_category, change.item_id, change.old_category),
            )
            if cursor.rowcount != 1:
                raise MigrationValidationError(
                    f"Item rowcount mismatch for id {change.item_id}: {cursor.rowcount}"
                )
        for change in plan.rule_updates:
            cursor = conn.execute(
                """
                UPDATE product_category_rules
                SET category = ?, updated_at = ?
                WHERE product_key = ? AND category = ? AND source = ? AND updated_at = ?
                """,
                (
                    change.new_category,
                    timestamp,
                    change.product_key,
                    change.old_category,
                    change.old_source,
                    change.old_updated_at,
                ),
            )
            if cursor.rowcount != 1:
                raise MigrationValidationError(
                    f"Rule rowcount mismatch for {change.product_key}: {cursor.rowcount}"
                )
        for change in plan.rule_inserts:
            cursor = conn.execute(
                """
                INSERT INTO product_category_rules
                    (product_key, category, source, created_at, updated_at)
                SELECT ?, ?, 'manual', ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM product_category_rules WHERE product_key = ?
                )
                """,
                (
                    change.product_key,
                    change.category,
                    timestamp,
                    timestamp,
                    change.product_key,
                ),
            )
            if cursor.rowcount != 1:
                raise MigrationValidationError(
                    f"Rule insert rowcount mismatch for {change.product_key}: {cursor.rowcount}"
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _table_columns(conn, table):
    return tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{table}")'))


def _rows_by_key(conn, table, key):
    columns = _table_columns(conn, table)
    key_index = columns.index(key)
    rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()
    return columns, {row[key_index]: row for row in rows}


def verify_database_diff(backup_path, database_path, plan):
    with closing(_read_only_connection(backup_path, immutable=True)) as before, closing(
        _read_only_connection(database_path, immutable=True)
    ) as after:
        before_schema = before.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        after_schema = after.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
        if before_schema != after_schema:
            raise MigrationValidationError("Database schema changed")
        if before.execute("SELECT * FROM receipts ORDER BY id").fetchall() != after.execute(
            "SELECT * FROM receipts ORDER BY id"
        ).fetchall():
            raise MigrationValidationError("Receipt data changed")

        item_columns, before_items = _rows_by_key(before, "items", "id")
        after_item_columns, after_items = _rows_by_key(after, "items", "id")
        if item_columns != after_item_columns or before_items.keys() != after_items.keys():
            raise MigrationValidationError("Item rows or columns changed")
        changed_item_ids = []
        changed_item_fields = set()
        for item_id in sorted(before_items):
            old = before_items[item_id]
            new = after_items[item_id]
            fields = {
                column
                for column, old_value, new_value in zip(item_columns, old, new)
                if old_value != new_value
            }
            if fields:
                changed_item_ids.append(item_id)
                changed_item_fields.update(fields)
                if fields != {"category"}:
                    raise MigrationValidationError(
                        f"Out-of-scope item fields changed for {item_id}: {sorted(fields)}"
                    )
        expected_item_ids = [change.item_id for change in plan.item_changes]
        if changed_item_ids != expected_item_ids:
            raise MigrationValidationError("Changed item IDs differ from migration plan")

        rule_columns, before_rules = _rows_by_key(before, "product_category_rules", "product_key")
        after_rule_columns, after_rules = _rows_by_key(after, "product_category_rules", "product_key")
        if rule_columns != after_rule_columns:
            raise MigrationValidationError("Rule columns changed")
        deleted_keys = before_rules.keys() - after_rules.keys()
        if deleted_keys:
            raise MigrationValidationError(f"Rules deleted: {sorted(deleted_keys)}")
        inserted_keys = sorted(after_rules.keys() - before_rules.keys())
        expected_inserted = sorted(change.product_key for change in plan.rule_inserts)
        if inserted_keys != expected_inserted:
            raise MigrationValidationError("Inserted rule keys differ from migration plan")

        updated_keys = []
        changed_rule_fields = set()
        for product_key in sorted(before_rules.keys() & after_rules.keys()):
            old = before_rules[product_key]
            new = after_rules[product_key]
            fields = {
                column
                for column, old_value, new_value in zip(rule_columns, old, new)
                if old_value != new_value
            }
            if fields:
                updated_keys.append(product_key)
                changed_rule_fields.update(fields)
                if fields - {"category", "updated_at"}:
                    raise MigrationValidationError(
                        f"Out-of-scope rule fields changed for {product_key}: {sorted(fields)}"
                    )
        expected_updated = sorted(change.product_key for change in plan.rule_updates)
        if updated_keys != expected_updated:
            raise MigrationValidationError("Updated rule keys differ from migration plan")

    return DiffSummary(
        changed_item_ids=tuple(changed_item_ids),
        changed_item_fields=tuple(sorted(changed_item_fields)),
        updated_rule_keys=tuple(updated_keys),
        inserted_rule_keys=tuple(inserted_keys),
        changed_rule_fields=tuple(sorted(changed_rule_fields)),
    )


def database_snapshot(path, immutable=True):
    with closing(_read_only_connection(path, immutable=immutable)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        receipts = conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
        items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        rules = conn.execute("SELECT COUNT(*) FROM product_category_rules").fetchone()[0]
        identities = conn.execute(
            f"SELECT COUNT(DISTINCT {effective_product_identity_sql('')}) FROM items"
        ).fetchone()[0]
        spend = conn.execute(
            "SELECT COALESCE(SUM(COALESCE(line_total, price, 0)), 0) FROM items"
        ).fetchone()[0]
        categories = conn.execute(
            "SELECT category, COUNT(*) FROM items GROUP BY category ORDER BY category"
        ).fetchall()
    return DatabaseSnapshot(
        path=str(Path(path).resolve()),
        sha256=_sha256(path),
        integrity=integrity,
        receipts=receipts,
        items=items,
        rules=rules,
        effective_identities=identities,
        total_spend=round(float(spend or 0), 2),
        raw_categories=tuple((category, count) for category, count in categories),
    )


def verify_backup(production, backup):
    if backup.integrity != "ok":
        raise MigrationValidationError(f"Backup integrity failed: {backup.integrity}")
    fields = ("receipts", "items", "rules", "effective_identities", "total_spend", "raw_categories")
    mismatches = [field for field in fields if getattr(production, field) != getattr(backup, field)]
    if mismatches:
        raise MigrationValidationError(f"Backup differs from production: {mismatches}")


def restore_from_backup(backup_path, database_path):
    with closing(_read_only_connection(backup_path)) as source, closing(
        sqlite3.connect(Path(database_path).resolve())
    ) as target:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MigrationValidationError("Restored database integrity failed")


def _validate_expected_production(snapshot, plan):
    expected_snapshot = (374, 3701, 142, 1403)
    actual_snapshot = (
        snapshot.receipts,
        snapshot.items,
        snapshot.rules,
        snapshot.effective_identities,
    )
    if actual_snapshot != expected_snapshot:
        raise MigrationValidationError(
            f"Production snapshot drift: {actual_snapshot} != {expected_snapshot}"
        )
    expected_operations = {
        "LABEL_ONLY": 743,
        "CREATE_EXACT_RULE": 556,
        "UPDATE_EXISTING_RULE": 19,
        "MULTI_RULE_EXACT": 26,
    }
    if plan.identity_count != 1344 or len(plan.item_changes) != 3563:
        raise MigrationValidationError(
            f"SAFE scope drift: {plan.identity_count} identities / {len(plan.item_changes)} rows"
        )
    if dict(plan.operation_counts) != expected_operations:
        raise MigrationValidationError(
            f"Operation inventory drift: {dict(plan.operation_counts)}"
        )


def _main_payload(snapshot, plan, backup=None, after=None, diff=None):
    payload = {
        "before": asdict(snapshot),
        "plan": plan.summary(),
        "update_existing_rules": [asdict(change) for change in plan.rule_updates],
        "multi_rule_exact": [
            {
                "effective_product": candidate.effective_product,
                "product_key": candidate.product_key,
                "raw_alias_keys": candidate.predicates["raw_alias_keys"],
                "target_category": candidate.target_category,
                "reason": candidate.reason,
            }
            for candidate in plan.candidates
            if candidate.expected_rule_operation == "MULTI_RULE_EXACT"
        ],
    }
    if backup:
        payload["backup"] = asdict(backup)
    if after:
        payload["after"] = asdict(after)
    if diff:
        payload["diff"] = asdict(diff)
    return payload


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(DB_PATH),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/audits/2026-08-14-category-taxonomy-v2-safe-migration-candidates.csv"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_path = args.database.resolve()
    before = database_snapshot(database_path)
    candidates = load_manifest(args.manifest)
    with closing(_read_only_connection(database_path, immutable=True)) as conn:
        plan = build_migration_plan(conn, candidates)
    _validate_expected_production(before, plan)
    if not args.apply:
        print(json.dumps(_main_payload(before, plan), ensure_ascii=False, indent=2))
        return

    backup_path = backup_database("category_taxonomy_v2")
    backup = database_snapshot(backup_path)
    verify_backup(before, backup)
    committed = False
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            apply_migration_plan(conn, plan)
        committed = True
        diff = verify_database_diff(backup_path, database_path, plan)
        after = database_snapshot(database_path, immutable=False)
        if after.integrity != "ok":
            raise MigrationValidationError(f"Post-write integrity failed: {after.integrity}")
        if (
            after.receipts != before.receipts
            or after.items != before.items
            or after.effective_identities != before.effective_identities
            or after.total_spend != before.total_spend
        ):
            raise MigrationValidationError("Post-write invariant failed")
    except Exception:
        if committed:
            restore_from_backup(backup_path, database_path)
        raise

    print(
        json.dumps(
            _main_payload(before, plan, backup=backup, after=after, diff=diff),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
