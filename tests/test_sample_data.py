import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import config, db
from app.create_sample_db import create_sample_database


SAMPLE_SOURCE = Path(__file__).resolve().parents[1] / "sample_data" / "receipts.json"


class SampleDataTests(unittest.TestCase):
    def test_creates_representative_sample_and_restores_database_path(self):
        original_db_path = db.DB_PATH

        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "nested" / "sample.db"

            counts = create_sample_database(SAMPLE_SOURCE, target)

            self.assertEqual(counts, {"receipts": 3, "items": 7})
            self.assertEqual(db.DB_PATH, original_db_path)
            with closing(sqlite3.connect(target)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 3)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 7)
                recurring = conn.execute(
                    """
                    SELECT COUNT(*), COUNT(DISTINCT receipts.store),
                           MIN(items.normalized_unit_price), MAX(items.normalized_unit_price)
                    FROM items JOIN receipts ON receipts.id = items.receipt_id
                    WHERE items.normalized_name = 'synthetic grain squares 500g'
                    """
                ).fetchone()
                weighted = conn.execute(
                    """
                    SELECT normalized_name, quantity_unit, normalized_unit_price,
                           normalized_price_unit, price_parse_source, price_parse_confidence,
                           category
                    FROM items WHERE name = 'Synthetic Orchard Cubes kg'
                    """
                ).fetchone()
                packaged = conn.execute(
                    """
                    SELECT package_size, package_unit, normalized_unit_price,
                           normalized_price_unit, price_parse_source, price_parse_confidence,
                           category
                    FROM items WHERE name = 'Synthetic Grain Squares 500g'
                    """
                ).fetchone()

            self.assertEqual(
                weighted,
                (
                    "synthetic orchard cubes kg",
                    "kg",
                    4.0,
                    "eur_per_kg",
                    "weighted_inference",
                    0.75,
                    "овощи и фрукты",
                ),
            )
            self.assertEqual(
                packaged,
                (500.0, "g", 3.0, "eur_per_kg", "package_name", 0.85, "бакалея и основные продукты"),
            )
            self.assertEqual(recurring, (2, 2, 3.0, 3.5))

    def test_refuses_existing_and_production_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.db"
            target.touch()

            with self.assertRaises(FileExistsError):
                create_sample_database(SAMPLE_SOURCE, target)
            with self.assertRaises(ValueError):
                create_sample_database(SAMPLE_SOURCE, config.DATA_DIR / 'receipts.db')

    def test_rejects_non_synthetic_and_empty_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "sample.db"
            for filename, payload in (
                ("unmarked.json", {"synthetic": False, "receipts": [{}]}),
                ("empty.json", {"synthetic": True, "receipts": []}),
                ("wrong-type.json", {"synthetic": True, "receipts": "not-a-list"}),
            ):
                source = root / filename
                source.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(filename=filename), self.assertRaises(ValueError):
                    create_sample_database(source, target)


if __name__ == "__main__":
    unittest.main()
