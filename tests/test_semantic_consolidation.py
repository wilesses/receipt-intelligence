import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

import app.db as db
from app.analytics_service import get_item_trend
from app.web.app import create_app


class SemanticConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "semantic-consolidation.db"
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_purchase(
        self,
        name,
        *,
        canonical_name=None,
        normalized_name=None,
        date="2026-06-10",
        price=2.0,
    ):
        with db.get_connection() as conn:
            receipt = conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, 'RIMI', ?, ?)",
                (date, price, f"semantic-{conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]}"),
            )
            conn.execute(
                """
                INSERT INTO items (
                    receipt_id, name, normalized_name, canonical_name,
                    quantity, price, line_total, unit_price, quantity_unit,
                    package_size, package_unit, normalized_unit_price,
                    normalized_price_unit, price_parse_source,
                    price_parse_confidence, category
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, 'piece', 1, 'piece', ?,
                          'eur_per_piece', 'package_name', 0.95, 'прочее')
                """,
                (
                    receipt.lastrowid,
                    name,
                    normalized_name or name.casefold(),
                    canonical_name,
                    price,
                    price,
                    price,
                    price,
                ),
            )
            conn.commit()

    def test_normalized_name_does_not_merge_exact_trend_identities(self):
        self.add_purchase("Milk", normalized_name="milk", price=2)
        self.add_purchase("Milk Deluxe", normalized_name="milk", price=8)

        result = get_item_trend("Milk")

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["values"], [2.0])
        self.assertEqual(result["unit_label"], "€/шт.")

    def test_raw_canonical_alias_resolves_to_full_canonical_dossier(self):
        self.add_purchase(
            "Raw alias one",
            canonical_name="Shared canonical",
            date="2026-06-10",
            price=2,
        )
        self.add_purchase(
            "Raw alias two",
            canonical_name="Shared canonical",
            date="2026-07-10",
            price=3,
        )

        trend = get_item_trend("Shared canonical")
        response = self.client.get(f"/item/{quote('Raw alias one', safe='')}")
        html = response.get_data(as_text=True)

        self.assertEqual(trend["labels"], ["2026-06", "2026-07"])
        self.assertEqual(trend["values"], [2.0, 3.0])
        self.assertIn("2 записей", html)
        self.assertIn("Raw alias one", html)
        self.assertIn("Raw alias two", html)

    def test_dossier_removes_legacy_average_and_labels_normalized_trend(self):
        self.add_purchase("Semantic product", price=2)
        html = self.client.get("/item/Semantic%20product").get_data(as_text=True)

        self.assertNotIn("<dt>Средняя цена</dt>", html)
        self.assertIn("<dt>Потрачено всего</dt>", html)
        self.assertIn("Медианная сопоставимая цена по месяцам", html)
        self.assertNotIn("Без приведения к размеру упаковки", html)


if __name__ == "__main__":
    unittest.main()
