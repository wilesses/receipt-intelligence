import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app.backfill_normalized_names as normalized_backfill
import app.backfill_price_data as price_backfill
import app.db as db
from app.price_model import ParsedPriceData


DISALLOWED_ITEM_FIELDS = [
    "id",
    "receipt_id",
    "name",
    "quantity",
    "price",
    "category",
    "category_source",
    "canonical_name",
]

PRICE_TARGET_FIELDS = price_backfill.TARGET_FIELDS


class BackfillSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.create_tables()
        self.backup_dir = Path(self.tmpdir.name) / "backups"

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_receipt(self):
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, ?, ?, ?)",
                ("2026-01-01", "TEST", 0, f"r-{id(self)}"),
            )
            conn.commit()
            return conn.execute("SELECT id FROM receipts ORDER BY id DESC LIMIT 1").fetchone()[0]

    def add_item(self, receipt_id, **overrides):
        values = {
            "receipt_id": receipt_id,
            "name": "Coca-Cola 500ml",
            "canonical_name": "Manual Coca",
            "normalized_name": None,
            "quantity": 2,
            "price": 3,
            "line_total": None,
            "unit_price": None,
            "quantity_unit": None,
            "package_size": None,
            "package_unit": None,
            "normalized_unit_price": None,
            "normalized_price_unit": None,
            "price_parse_source": None,
            "price_parse_confidence": None,
            "category": "напитки",
            "category_source": "manual",
        }
        values.update(overrides)
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO items (
                    receipt_id, name, canonical_name, normalized_name, quantity, price,
                    line_total, unit_price, quantity_unit, package_size, package_unit,
                    normalized_unit_price, normalized_price_unit, price_parse_source,
                    price_parse_confidence, category, category_source
                )
                VALUES (
                    :receipt_id, :name, :canonical_name, :normalized_name, :quantity, :price,
                    :line_total, :unit_price, :quantity_unit, :package_size, :package_unit,
                    :normalized_unit_price, :normalized_price_unit, :price_parse_source,
                    :price_parse_confidence, :category, :category_source
                )
                """,
                values,
            )
            conn.commit()
            return conn.execute("SELECT id FROM items ORDER BY id DESC LIMIT 1").fetchone()[0]

    def snapshot(self):
        with db.get_connection() as conn:
            item_rows = conn.execute("SELECT * FROM items ORDER BY id").fetchall()
            item_columns = [column[0] for column in conn.execute("SELECT * FROM items LIMIT 0").description]
            rule_rows = conn.execute("SELECT * FROM product_category_rules ORDER BY id").fetchall()
            rule_columns = [column[0] for column in conn.execute("SELECT * FROM product_category_rules LIMIT 0").description]
        return {
            "items": [dict(zip(item_columns, row)) for row in item_rows],
            "rules": [dict(zip(rule_columns, row)) for row in rule_rows],
        }

    def schema_snapshot(self):
        with db.get_connection() as conn:
            objects = conn.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            ).fetchall()
            tables = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
            columns = {
                table_name: conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
                for (table_name,) in tables
            }
        return {"objects": objects, "columns": columns}

    def add_manual_rule(self):
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO product_category_rules (product_key, category, source, created_at, updated_at)
                VALUES ('coca cola 500ml', 'напитки', 'manual', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
                """
            )
            conn.commit()

    def test_dry_run_does_not_change_database(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id)
        self.add_manual_rule()
        before = self.snapshot()

        normalized_result = normalized_backfill.backfill_normalized_names()
        price_result = price_backfill.backfill_price_data()

        self.assertTrue(normalized_result["dry_run"])
        self.assertTrue(price_result["dry_run"])
        self.assertEqual(before, self.snapshot())

    def test_repeated_dry_run_preserves_file_logical_state_mtime_and_backup_directory(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id)
        self.add_manual_rule()
        self.backup_dir.mkdir()

        before_bytes = db.DB_PATH.read_bytes()
        before_mtime = db.DB_PATH.stat().st_mtime_ns
        before_snapshot = self.snapshot()
        before_backups = list(self.backup_dir.iterdir())

        for _ in range(2):
            normalized_backfill.backfill_normalized_names(backup_dir=self.backup_dir)
            price_backfill.backfill_price_data(backup_dir=self.backup_dir)

        self.assertEqual(db.DB_PATH.read_bytes(), before_bytes)
        self.assertEqual(db.DB_PATH.stat().st_mtime_ns, before_mtime)
        self.assertEqual(self.snapshot(), before_snapshot)
        self.assertEqual(list(self.backup_dir.iterdir()), before_backups)

    def test_apply_changes_only_allowed_fields_and_preserves_manual_data(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id)
        self.add_manual_rule()
        before = self.snapshot()

        normalized_backfill.backfill_normalized_names(apply=True, backup_dir=self.backup_dir)
        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)
        after = self.snapshot()

        self.assertEqual(before["rules"], after["rules"])
        for before_item, after_item in zip(before["items"], after["items"]):
            for field in DISALLOWED_ITEM_FIELDS:
                self.assertEqual(before_item[field], after_item[field], field)

        item = after["items"][0]
        self.assertEqual(item["normalized_name"], "coca cola 500ml")
        self.assertEqual(item["line_total"], 3)
        self.assertEqual(item["quantity_unit"], "piece")
        self.assertEqual(item["normalized_price_unit"], "eur_per_l")
        self.assertTrue(list(self.backup_dir.glob("*.db")))

    def test_repeated_apply_is_idempotent(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id)

        normalized_backfill.backfill_normalized_names(apply=True, backup_dir=self.backup_dir)
        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)
        first = self.snapshot()

        normalized_result = normalized_backfill.backfill_normalized_names(apply=True, backup_dir=self.backup_dir)
        price_result = price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )

        self.assertEqual(first, self.snapshot())
        self.assertEqual(normalized_result["stats"].get("to_update", 0), 0)
        self.assertEqual(price_result["stats"].get("to_update", 0), 0)

    def test_price_write_abort_on_second_item_rolls_back_first_item(self):
        receipt_id = self.add_receipt()
        first_id = self.add_item(receipt_id, name="Coca-Cola 500ml")
        second_id = self.add_item(receipt_id, name="Pepsi 500ml")
        self.add_manual_rule()
        before = self.snapshot()

        with db.get_connection() as conn:
            conn.execute(
                f"""
                CREATE TRIGGER abort_second_price_update
                BEFORE UPDATE ON items
                WHEN OLD.id = {second_id}
                BEGIN
                    SELECT RAISE(ABORT, 'second item rejected');
                END
                """
            )
            conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            price_backfill.backfill_price_data(
                apply=True, sources={"package_name"}, backup_dir=self.backup_dir
            )

        self.assertEqual(before, self.snapshot())
        self.assertIsNone(
            next(item for item in self.snapshot()["items"] if item["id"] == first_id)["line_total"]
        )

    def test_existing_higher_confidence_is_not_overwritten(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            line_total=3,
            unit_price=1.5,
            quantity_unit="piece",
            package_size=500,
            package_unit="ml",
            normalized_unit_price=3,
            normalized_price_unit="eur_per_l",
            price_parse_source="parser",
            price_parse_confidence=0.95,
        )

        result = price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )
        item = self.snapshot()["items"][0]

        self.assertEqual(result["stats"].get("to_update", 0), 0)
        self.assertEqual(item["price_parse_source"], "parser")
        self.assertEqual(item["price_parse_confidence"], 0.95)

    def test_selective_package_apply_does_not_downgrade_existing_eur_per_piece(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            name="Olas 30gab",
            quantity=1,
            price=2.99,
            line_total=2.99,
            unit_price=2.99,
            quantity_unit="piece",
            package_size=30,
            package_unit="piece",
            normalized_unit_price=0.10,
            normalized_price_unit="eur_per_piece",
            price_parse_source="parser",
            price_parse_confidence=0.95,
        )

        result = price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )
        item = self.snapshot()["items"][0]

        self.assertEqual(result["stats"].get("to_update", 0), 0)
        self.assertEqual(item["normalized_unit_price"], 0.10)
        self.assertEqual(item["normalized_price_unit"], "eur_per_piece")
        self.assertEqual(item["price_parse_source"], "parser")
        self.assertEqual(item["price_parse_confidence"], 0.95)

    def test_read_only_audit_reports_service_conflict_with_existing_high_confidence_data(self):
        receipt_id = self.add_receipt()
        item_id = self.add_item(
            receipt_id,
            name="Papīra iepirkumu maisiņš PALDIES",
            line_total=0.19,
            unit_price=0.19,
            quantity_unit="piece",
            package_size=None,
            package_unit="unknown",
            normalized_unit_price=0.19,
            normalized_price_unit="eur_per_piece",
            price_parse_source="parser",
            price_parse_confidence=0.95,
        )
        before = self.snapshot()

        result = price_backfill.plan_price_data_backfill()

        self.assertIn("high_confidence_conflicts", result)
        conflict = next(entry for entry in result["high_confidence_conflicts"] if entry["id"] == item_id)
        self.assertEqual(conflict["before"]["price_parse_confidence"], 0.95)
        self.assertEqual(conflict["verdict"], "service_line")
        self.assertIn("service_line", conflict["reasons"])
        self.assertIn(conflict["recommended_action"], {"preserve", "manual review", "clear later"})
        self.assertEqual(before, self.snapshot())

    def test_low_confidence_service_line_is_planned_as_unresolved(self):
        receipt_id = self.add_receipt()
        item_id = self.add_item(
            receipt_id,
            name="Papildus depozīta maksa",
            line_total=0.10,
            unit_price=0.10,
            quantity_unit="piece",
            normalized_unit_price=0.10,
            normalized_price_unit="eur_per_piece",
            price_parse_source="inferred_piece",
            price_parse_confidence=0.70,
        )

        result = price_backfill.plan_price_data_backfill()
        item = next(entry for entry in result["examples"] if entry["id"] == item_id)

        self.assertEqual(item["after"]["quantity_unit"], "unknown")
        self.assertIsNone(item["after"]["normalized_unit_price"])
        self.assertEqual(item["after"]["normalized_price_unit"], "unknown")
        self.assertEqual(item["after"]["price_parse_source"], "service_line")
        self.assertIsNone(item["after"]["price_parse_confidence"])

    def test_nonselected_weaker_candidate_does_not_fill_high_confidence_row(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            name="Siers 500g",
            line_total=8,
            unit_price=3.75,
            quantity_unit="piece",
            package_size=None,
            package_unit="",
            normalized_unit_price=15,
            normalized_price_unit="eur_per_kg",
            price_parse_source="parser",
            price_parse_confidence=0.95,
        )

        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)
        item = self.snapshot()["items"][0]

        self.assertEqual(item["line_total"], 8)
        self.assertEqual(item["unit_price"], 3.75)
        self.assertEqual(item["quantity_unit"], "piece")
        self.assertEqual(item["normalized_unit_price"], 15)
        self.assertEqual(item["normalized_price_unit"], "eur_per_kg")
        self.assertEqual(item["price_parse_source"], "parser")
        self.assertEqual(item["price_parse_confidence"], 0.95)
        self.assertIsNone(item["package_size"])
        self.assertEqual(item["package_unit"], "")

    def test_uninformative_candidate_values_do_not_erase_existing_fields(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            name="Mystery item",
            line_total=9,
            unit_price=4.5,
            quantity_unit="kg",
            package_size=250,
            package_unit="g",
            normalized_unit_price=36,
            normalized_price_unit="eur_per_kg",
            price_parse_source="manual_import",
            price_parse_confidence=0.1,
        )

        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)
        item = self.snapshot()["items"][0]

        self.assertEqual(item["quantity_unit"], "kg")
        self.assertEqual(item["package_size"], 250)
        self.assertEqual(item["package_unit"], "g")
        self.assertEqual(item["normalized_unit_price"], 36)
        self.assertEqual(item["normalized_price_unit"], "eur_per_kg")

    def test_empty_candidate_values_do_not_erase_existing_fields(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            name="Imported item",
            line_total=9,
            unit_price=4.5,
            quantity_unit="piece",
            package_size=250,
            package_unit="g",
            normalized_unit_price=36,
            normalized_price_unit="eur_per_kg",
            price_parse_source="manual_import",
            price_parse_confidence=0.1,
        )
        candidate = ParsedPriceData(
            quantity=2,
            quantity_unit="",
            line_total=9,
            unit_price=4.5,
            package_size=None,
            package_unit="",
            normalized_unit_price=None,
            normalized_price_unit="unknown",
            source="",
            confidence=0.9,
        )

        with patch.object(price_backfill, "derive_price_data", return_value=candidate):
            price_backfill.backfill_price_data(
                apply=True, sources={"package_name"}, backup_dir=self.backup_dir
            )
        item = self.snapshot()["items"][0]

        self.assertEqual(item["quantity_unit"], "piece")
        self.assertEqual(item["package_size"], 250)
        self.assertEqual(item["package_unit"], "g")
        self.assertEqual(item["normalized_unit_price"], 36)
        self.assertEqual(item["normalized_price_unit"], "eur_per_kg")
        self.assertEqual(item["price_parse_source"], "manual_import")

    def test_mixed_row_updates_only_improved_price_fields_and_preserves_manual_data(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            name="Siers 500g",
            line_total=None,
            unit_price=1.5,
            quantity_unit="unknown",
            package_size=500,
            package_unit="g",
            normalized_unit_price=None,
            normalized_price_unit="unknown",
            price_parse_source=None,
            price_parse_confidence=None,
        )
        self.add_manual_rule()
        before = self.snapshot()

        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)
        after = self.snapshot()
        item = after["items"][0]

        self.assertEqual(item["line_total"], 3)
        self.assertEqual(item["unit_price"], 1.5)
        self.assertEqual(item["quantity_unit"], "piece")
        self.assertEqual(item["package_size"], 500)
        self.assertEqual(item["package_unit"], "g")
        self.assertEqual(item["normalized_unit_price"], 3)
        self.assertEqual(item["normalized_price_unit"], "eur_per_kg")
        for field in DISALLOWED_ITEM_FIELDS:
            self.assertEqual(before["items"][0][field], item[field], field)
        self.assertEqual(before["rules"], after["rules"])

    def test_sqlite_backup_contains_uncheckpointed_committed_wal_content(self):
        with db.get_connection() as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode = WAL").fetchone()[0], "wal")
            writer.execute("PRAGMA wal_autocheckpoint = 0")
            writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            writer.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, ?, ?, ?)",
                ("2026-02-02", "WAL TEST", 1, "latest-wal-row"),
            )
            writer.commit()
            self.assertTrue(Path(f"{db.DB_PATH}-wal").exists())

            for module in (normalized_backfill, price_backfill):
                with self.subTest(module=module.__name__):
                    module_backup_dir = self.backup_dir / module.__name__.rsplit(".", 1)[-1]
                    backup_path = module.create_backup(module_backup_dir)
                    with closing(sqlite3.connect(backup_path)) as backup:
                        self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                        row = backup.execute(
                            "SELECT store FROM receipts WHERE receipt_number = ?",
                            ("latest-wal-row",),
                        ).fetchone()
                    self.assertEqual(row, ("WAL TEST",))

    def test_successful_backfills_do_not_change_schema(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id)
        before = self.schema_snapshot()

        normalized_backfill.backfill_normalized_names(apply=True, backup_dir=self.backup_dir)
        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)

        self.assertEqual(self.schema_snapshot(), before)

    def test_zero_quantity_is_safe_and_unresolved(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id, name="Siers 500g", quantity=0, price=4)

        result = price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )
        item = self.snapshot()["items"][0]

        self.assertEqual(result["stats"].get("to_update", 0), 0)
        self.assertEqual(item["quantity"], 0)
        self.assertIsNone(item["normalized_price_unit"])
        self.assertIsNone(item["normalized_unit_price"])
        self.assertIsNone(item["price_parse_confidence"])

    def test_imported_parser_package_metadata_has_priority(self):
        added = db.add_receipt_with_items(
            "2026-03-03",
            "TEST",
            9,
            "parser-package",
            [{
                "name": "Siers bez izmēra nosaukumā",
                "quantity": 2,
                "price": 9,
                "line_total": 9,
                "unit_price": 4.5,
                "quantity_unit": "gab",
                "package_size": 750,
                "package_unit": "g",
                "price_parse_source": "parser",
            }],
        )

        self.assertTrue(added)
        with db.get_connection() as conn:
            item = conn.execute(
                """
                SELECT package_size, package_unit, normalized_unit_price,
                       normalized_price_unit, price_parse_source, price_parse_confidence
                FROM items WHERE name = ?
                """,
                ("Siers bez izmēra nosaukumā",),
            ).fetchone()
        self.assertEqual(item, (750, "g", 6, "eur_per_kg", "parser", 0.95))

    def test_weighted_inference_confidence_survives_persistence(self):
        added = db.add_receipt_with_items(
            "2026-03-04",
            "TEST",
            5.93,
            "weighted-inference",
            [{
                "name": "Siers kg",
                "quantity": 0.742,
                "price": 5.93,
                "line_total": 5.93,
                "unit_price": 7.99,
                "quantity_unit": "kg",
                "source": "weighted_inference",
            }],
        )

        self.assertTrue(added)
        with db.get_connection() as conn:
            source, confidence = conn.execute(
                "SELECT price_parse_source, price_parse_confidence FROM items WHERE name = 'Siers kg'"
            ).fetchone()
        self.assertEqual(source, "weighted_inference")
        self.assertEqual(confidence, 0.75)

    def test_complete_compatible_row_gets_missing_metadata(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            name="Siers 500g",
            line_total=3,
            unit_price=1.5,
            quantity_unit="piece",
            package_size=500,
            package_unit="g",
            normalized_unit_price=3,
            normalized_price_unit="eur_per_kg",
            price_parse_source=None,
            price_parse_confidence=None,
        )

        price_backfill.backfill_price_data(apply=True, sources={"package_name"}, backup_dir=self.backup_dir)
        item = self.snapshot()["items"][0]
        self.assertIsNone(item["price_parse_source"])
        self.assertIsNone(item["price_parse_confidence"])

    def _add_selective_candidates(self):
        receipt_id = self.add_receipt()
        package_id = self.add_item(receipt_id, name="Siers 500g", quantity=1, price=5)
        weighted_id = self.add_item(
            receipt_id, name="Āboli kg", quantity=0.5, price=2, unit_price=4
        )
        return package_id, weighted_id

    def test_selective_apply_only_package_name(self):
        package_id, weighted_id = self._add_selective_candidates()

        price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )
        items = {item["id"]: item for item in self.snapshot()["items"]}

        self.assertEqual(items[package_id]["price_parse_source"], "package_name")
        self.assertIsNone(items[weighted_id]["price_parse_source"])

    def test_selective_apply_only_weighted_inference(self):
        package_id, weighted_id = self._add_selective_candidates()

        price_backfill.backfill_price_data(
            apply=True, sources={"weighted_inference"}, backup_dir=self.backup_dir
        )
        items = {item["id"]: item for item in self.snapshot()["items"]}

        self.assertIsNone(items[package_id]["price_parse_source"])
        self.assertEqual(items[weighted_id]["price_parse_source"], "weighted_inference")
        self.assertEqual(items[weighted_id]["price_parse_confidence"], 0.75)

    def test_weighted_inference_upgrades_weaker_existing_metadata(self):
        receipt_id = self.add_receipt()
        item_id = self.add_item(
            receipt_id,
            name="Āboli kg",
            quantity=0.5,
            price=2,
            unit_price=4,
            quantity_unit="unknown",
            normalized_price_unit="unknown",
            price_parse_source="parser",
            price_parse_confidence=0.65,
        )

        price_backfill.backfill_price_data(
            apply=True, sources={"weighted_inference"}, backup_dir=self.backup_dir
        )
        item = next(item for item in self.snapshot()["items"] if item["id"] == item_id)

        self.assertEqual(item["price_parse_source"], "weighted_inference")
        self.assertEqual(item["price_parse_confidence"], 0.75)

    def test_selective_apply_accepts_both_safe_sources(self):
        package_id, weighted_id = self._add_selective_candidates()

        price_backfill.backfill_price_data(
            apply=True,
            sources={"package_name", "weighted_inference"},
            backup_dir=self.backup_dir,
        )
        items = {item["id"]: item for item in self.snapshot()["items"]}

        self.assertEqual(items[package_id]["price_parse_source"], "package_name")
        self.assertEqual(items[weighted_id]["price_parse_source"], "weighted_inference")

    def test_selective_apply_excludes_unsafe_and_conflicting_rows(self):
        receipt_id = self.add_receipt()
        ids = [
            self.add_item(receipt_id, name="Krūze", quantity=1, price=2),
            self.add_item(receipt_id, name="Papildus depozīta maksa", quantity=1, price=0.1),
            self.add_item(receipt_id, name="Čeks 123/456 Piens 1L", quantity=1, price=1),
            self.add_item(
                receipt_id,
                name="Burgeru maizītes Rustico 4gab. 300g",
                quantity=1,
                price=1.52,
                line_total=1.52,
                unit_price=1.52,
                quantity_unit="piece",
                package_size=300,
                package_unit="g",
                normalized_unit_price=5.0667,
                normalized_price_unit="eur_per_kg",
                price_parse_source="derived",
                price_parse_confidence=0.95,
            ),
        ]
        before = {item["id"]: item for item in self.snapshot()["items"]}

        result = price_backfill.backfill_price_data(
            apply=True,
            sources={"package_name", "weighted_inference"},
            backup_dir=self.backup_dir,
        )
        after = {item["id"]: item for item in self.snapshot()["items"]}

        for item_id in ids:
            self.assertEqual(before[item_id], after[item_id])
        self.assertEqual(len(result["high_confidence_conflicts"]), 1)

    def test_selective_apply_rejects_missing_or_unknown_sources(self):
        with self.assertRaisesRegex(ValueError, "--sources"):
            price_backfill.backfill_price_data(apply=True, backup_dir=self.backup_dir)
        with self.assertRaisesRegex(ValueError, "Unknown source"):
            price_backfill.backfill_price_data(sources={"made_up"})
        self.assertFalse(self.backup_dir.exists())

    def test_selective_apply_is_idempotent_and_backup_is_valid(self):
        package_id, _ = self._add_selective_candidates()
        first = price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )
        first_snapshot = self.snapshot()
        second = price_backfill.backfill_price_data(
            apply=True, sources={"package_name"}, backup_dir=self.backup_dir
        )

        self.assertEqual(first_snapshot, self.snapshot())
        self.assertEqual(second["stats"].get("to_update", 0), 0)
        with closing(sqlite3.connect(first["backup_path"])) as backup:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertIsNone(
                backup.execute(
                    "SELECT price_parse_source FROM items WHERE id = ?", (package_id,)
                ).fetchone()[0]
            )

    def test_apply_and_dry_run_flags_are_mutually_exclusive(self):
        for module in (normalized_backfill, price_backfill):
            with self.subTest(module=module.__name__):
                with patch.object(sys, "argv", [module.__name__, "--apply", "--dry-run"]):
                    with self.assertRaises(SystemExit):
                        module.main()


if __name__ == "__main__":
    unittest.main()
