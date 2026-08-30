import csv
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.apply_category_taxonomy_v2 import (
    MigrationValidationError,
    apply_migration_plan,
    build_migration_plan,
    load_manifest,
    verify_database_diff,
)
from app.product_normalizer import normalize_product_name


class CategoryTaxonomyV2MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "receipts.db"
        self.manifest_path = self.root / "safe.csv"
        self._create_database()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_database(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE receipts (
                    id INTEGER PRIMARY KEY,
                    date TEXT,
                    store TEXT,
                    total REAL,
                    receipt_number TEXT
                );
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY,
                    receipt_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    canonical_name TEXT,
                    normalized_name TEXT,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    line_total REAL,
                    unit_price REAL,
                    quantity_unit TEXT,
                    package_size REAL,
                    package_unit TEXT,
                    normalized_unit_price REAL,
                    normalized_price_unit TEXT,
                    price_parse_source TEXT,
                    price_parse_confidence REAL,
                    category TEXT NOT NULL,
                    category_source TEXT NOT NULL
                );
                CREATE TABLE product_category_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_key TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO receipts VALUES (1, '2026-08-01', 'TEST', 12.0, 'R-1');
                """
            )
            conn.commit()

    def _insert_candidate_scope(self):
        effective = "Canonical Product 500g"
        canonical_key = normalize_product_name(effective)
        rows = [
            (1, "Raw Product A 500g", "мясо", "manual"),
            (2, "Raw Product B 500g", "мясо", "inherited"),
        ]
        with closing(sqlite3.connect(self.db_path)) as conn:
            for item_id, raw_name, category, source in rows:
                conn.execute(
                    """
                    INSERT INTO items (
                        id, receipt_id, name, canonical_name, normalized_name,
                        quantity, price, line_total, category, category_source
                    ) VALUES (?, 1, ?, ?, ?, 1, 6, 6, ?, ?)
                    """,
                    (
                        item_id,
                        raw_name,
                        effective,
                        normalize_product_name(raw_name),
                        category,
                        source,
                    ),
                )
            conn.execute(
                """
                INSERT INTO items (
                    id, receipt_id, name, normalized_name, quantity, price,
                    line_total, category, category_source
                ) VALUES (3, 1, 'Needs Review', 'needs review', 1, 0, 0, 'прочее', 'fallback')
                """
            )
            conn.execute(
                """
                INSERT INTO product_category_rules
                    (product_key, category, source, created_at, updated_at)
                VALUES (?, 'мясо', 'manual', '2026-01-01', '2026-01-01')
                """,
                (canonical_key,),
            )
            conn.commit()
        return effective, canonical_key, [normalize_product_name(row[1]) for row in rows]

    def _write_manifest(self, effective, canonical_key, raw_alias_keys, **overrides):
        predicate = {
            "current_categories": "мясо:2",
            "effective_product": effective,
            "existing_rule": "мясо|manual",
            "identity_row_count": 2,
            "item_exception_count": 0,
            "item_exception_ids": [],
            "product_key": canonical_key,
            "raw_alias_keys": raw_alias_keys,
            "rule_scope_rows": 2,
            "shared_product_key_identity_count": 1,
        }
        row = {
            "effective_product": effective,
            "product_key": canonical_key,
            "target_category": "мясо и птица",
            "current_categories": "мясо:2",
            "expected_affected_item_count": "2",
            "expected_rule_operation": "MULTI_RULE_EXACT",
            "before_state_predicates": json.dumps(predicate, ensure_ascii=False),
            "required_exact_exclusions": "",
            "protected_item_ids": "",
            "reason": "Exact synthetic fixture",
            "confidence": "HIGH",
        }
        row.update(overrides)
        with self.manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)

    def _backup(self):
        path = self.root / "backup.db"
        with closing(sqlite3.connect(self.db_path)) as source:
            with closing(sqlite3.connect(path)) as target:
                source.backup(target)
        return path

    def test_exact_apply_preserves_sources_and_excluded_rows(self):
        effective, canonical_key, raw_alias_keys = self._insert_candidate_scope()
        self._write_manifest(effective, canonical_key, raw_alias_keys)
        backup_path = self._backup()

        candidates = load_manifest(self.manifest_path)
        with closing(sqlite3.connect(self.db_path)) as conn:
            plan = build_migration_plan(conn, candidates)
            self.assertEqual(len(plan.item_changes), 2)
            self.assertEqual(len(plan.rule_updates), 1)
            self.assertEqual(len(plan.rule_inserts), 2)
            apply_migration_plan(conn, plan)

        with closing(sqlite3.connect(self.db_path)) as conn:
            items = conn.execute(
                "SELECT id, category, category_source FROM items ORDER BY id"
            ).fetchall()
            rules = conn.execute(
                "SELECT product_key, category, source FROM product_category_rules ORDER BY product_key"
            ).fetchall()
        self.assertEqual(
            items,
            [
                (1, "мясо и птица", "manual"),
                (2, "мясо и птица", "inherited"),
                (3, "прочее", "fallback"),
            ],
        )
        self.assertEqual({row[0] for row in rules}, {canonical_key, *raw_alias_keys})
        self.assertTrue(all(row[1:] == ("мясо и птица", "manual") for row in rules))

        diff = verify_database_diff(backup_path, self.db_path, plan)
        self.assertEqual(diff.changed_item_ids, (1, 2))
        self.assertEqual(diff.changed_item_fields, ("category",))
        self.assertEqual(diff.inserted_rule_keys, tuple(sorted(raw_alias_keys)))

    def test_before_state_mismatch_aborts_dry_run(self):
        effective, canonical_key, raw_alias_keys = self._insert_candidate_scope()
        self._write_manifest(
            effective,
            canonical_key,
            raw_alias_keys,
            current_categories="мясо:3",
        )

        with closing(sqlite3.connect(self.db_path)) as conn:
            with self.assertRaises(MigrationValidationError):
                build_migration_plan(conn, load_manifest(self.manifest_path))

    def test_rowcount_drift_rolls_back_whole_apply(self):
        effective, canonical_key, raw_alias_keys = self._insert_candidate_scope()
        self._write_manifest(effective, canonical_key, raw_alias_keys)
        candidates = load_manifest(self.manifest_path)

        with closing(sqlite3.connect(self.db_path)) as conn:
            plan = build_migration_plan(conn, candidates)
            conn.execute("UPDATE items SET category = 'дрейф' WHERE id = 2")
            conn.commit()
            with self.assertRaises(MigrationValidationError):
                apply_migration_plan(conn, plan)

        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(
                conn.execute("SELECT category FROM items WHERE id = 1").fetchone()[0],
                "мясо",
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM product_category_rules").fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main()
