import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.analytics_service import get_analytics_data


class AnalyticsInsightTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "analytics-test.db"
        db.create_tables()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_receipt(self, receipt_date, store, items):
        with db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, ?, ?, ?)",
                (receipt_date, store, sum(item["price"] for item in items), f"{receipt_date}-{store}"),
            )
            receipt_id = cursor.lastrowid
            for item in items:
                conn.execute(
                    """
                    INSERT INTO items (receipt_id, name, canonical_name, quantity, price, category)
                    VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (
                        receipt_id,
                        item["name"],
                        item.get("canonical_name"),
                        item["price"],
                        item["category"],
                    ),
                )
            conn.commit()

    def test_full_slice_has_deterministic_coverage_change_and_largest_category(self):
        self.add_receipt(
            "2026-05-10",
            "RIMI",
            [{"name": "Хлеб", "price": 20, "category": "продукты"}],
        )
        self.add_receipt(
            "2026-06-10",
            "RIMI",
            [{"name": "Хлеб", "price": 30, "category": "продукты"}],
        )
        self.add_receipt(
            "2026-06-12",
            "MAXIMA",
            [{"name": "Шампунь", "price": 10, "category": "быт"}],
        )

        result = get_analytics_data()
        summary = result["insight_summary"]

        self.assertEqual(summary["state"], "ready")
        self.assertLessEqual(len(summary["lines"]), 3)
        self.assertEqual(
            [line["type"] for line in summary["lines"]],
            ["coverage", "month_change", "largest_category"],
        )
        self.assertEqual(summary["lines"][0]["period_count"], 2)
        self.assertEqual(summary["lines"][0]["receipt_count"], 3)
        self.assertEqual(summary["lines"][1]["direction"], "increased")
        self.assertEqual(summary["lines"][1]["change_percent"], 100.0)
        self.assertEqual(summary["lines"][2]["category"], "продукты")
        self.assertEqual(summary["lines"][2]["amount"], 50.0)
        self.assertEqual(summary["lines"][2]["share_percent"], 83.3)

    def test_empty_slice_has_explicit_empty_state(self):
        result = get_analytics_data(start="2035-01-01", end="2035-01-31")

        self.assertEqual(result["insight_summary"]["state"], "empty")
        self.assertEqual(result["insight_summary"]["lines"], [])
        self.assertEqual(result["total_spent"], 0)
        self.assertEqual(result["monthly_average"], 0)

    def test_one_month_uses_peak_without_comparison(self):
        self.add_receipt(
            "2026-05-10",
            "RIMI",
            [{"name": "Молоко", "price": 12.34, "category": "продукты"}],
        )

        result = get_analytics_data()
        lines = result["insight_summary"]["lines"]

        self.assertNotIn("month_change", [line["type"] for line in lines])
        peak = next(line for line in lines if line["type"] == "peak_month")
        self.assertEqual(peak["month"], "2026-05")
        self.assertEqual(peak["amount"], 12.34)

    def test_two_month_comparison_handles_decrease(self):
        self.add_receipt(
            "2026-05-10",
            "RIMI",
            [{"name": "Товар", "price": 20, "category": "прочее"}],
        )
        self.add_receipt(
            "2026-06-10",
            "RIMI",
            [{"name": "Товар", "price": 10, "category": "прочее"}],
        )

        decreased = get_analytics_data()["insight_summary"]["lines"][1]
        self.assertEqual(decreased["type"], "month_change")
        self.assertEqual(decreased["direction"], "decreased")
        self.assertEqual(decreased["change_percent"], 50.0)

    def test_two_month_comparison_does_not_divide_by_zero(self):
        self.add_receipt(
            "2026-05-10",
            "RIMI",
            [{"name": "Товар", "price": 0, "category": "прочее"}],
        )
        self.add_receipt(
            "2026-06-10",
            "RIMI",
            [{"name": "Товар", "price": 10, "category": "прочее"}],
        )

        comparison = get_analytics_data()["insight_summary"]["lines"][1]

        self.assertEqual(comparison["type"], "comparison_unavailable")
        self.assertEqual(comparison["reason"], "zero_baseline")

    def test_active_filters_drive_summary_and_preserve_chart_datasets(self):
        self.add_receipt(
            "2026-05-10",
            "RIMI",
            [
                {"name": "Хлеб белый", "price": 4, "category": "продукты"},
                {"name": "Мыло", "price": 8, "category": "быт"},
            ],
        )
        self.add_receipt(
            "2026-06-10",
            "MAXIMA",
            [{"name": "Хлеб белый", "price": 6, "category": "продукты"}],
        )

        result = get_analytics_data(
            start="2026-05-01",
            end="2026-05-31",
            store="RIMI",
            category="продукты",
            item="Хлеб",
        )

        self.assertEqual(result["months"], {"labels": ["2026-05"], "values": [4.0]})
        self.assertEqual(result["categories"], {"labels": ["продукты"], "values": [4.0]})
        self.assertEqual(result["top"], {"labels": ["Хлеб белый"], "values": [4.0]})
        self.assertEqual(result["insight_summary"]["receipt_count"], 1)
        self.assertEqual(result["insight_summary"]["lines"][2]["share_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
