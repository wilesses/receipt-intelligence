import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.web.app import create_app


class PriceQualityWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.create_tables()
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_item(
        self,
        name,
        *,
        date="2026-08-01",
        store="TEST STORE",
        quantity=1,
        quantity_unit="piece",
        line_total=2.5,
        unit_price=2.5,
        package_size=1,
        package_unit="piece",
        normalized_unit_price=2.5,
        normalized_price_unit="eur_per_piece",
        confidence=0.95,
    ):
        with db.get_connection() as conn:
            receipt_number = f"quality-{conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]}"
            cursor = conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, ?, ?, ?)",
                (date, store, line_total or 0, receipt_number),
            )
            receipt_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO items (
                    receipt_id, name, quantity, price, line_total, unit_price,
                    quantity_unit, package_size, package_unit,
                    normalized_unit_price, normalized_price_unit,
                    price_parse_confidence, category, category_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'прочее', 'fallback')
                """,
                (
                    receipt_id,
                    name,
                    quantity,
                    line_total or 0,
                    line_total,
                    unit_price,
                    quantity_unit,
                    package_size,
                    package_unit,
                    normalized_unit_price,
                    normalized_price_unit,
                    confidence,
                ),
            )
            conn.commit()
        return receipt_id

    def test_direct_route_renders_diagnostic_workspace_and_coverage(self):
        receipt_id = self.add_item(
            "Очень длинное название товара для проверки диагностического переноса 4x125g",
            normalized_unit_price=None,
            normalized_price_unit="unknown",
            confidence=None,
        )
        self.add_item("Нормализованный товар 1L", quantity_unit="l", normalized_price_unit="eur_per_l")

        response = self.client.get("/data-quality/prices")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="price-quality-workspace"', html)
        self.assertIn('class="coverage-band"', html)
        self.assertIn("50.0%", html)
        self.assertIn("1 из 2 строк", html)
        self.assertIn("Техническое покрытие цены", html)
        self.assertIn('class="problem-selector"', html)
        self.assertIn('class="diagnostic-register"', html)
        self.assertIn("data-diagnostic-row", html)
        self.assertIn('data-label="Товар"', html)
        self.assertIn('data-label="Проблема"', html)
        self.assertIn('data-label="Технические данные"', html)
        self.assertIn(f'href="/receipt/{receipt_id}"', html)
        self.assertNotIn('class="metric-card"', html)
        self.assertNotIn("Unknown unit", html)
        self.assertNotIn("Low confidence", html)

    def test_existing_problem_filters_keep_their_backend_semantics(self):
        unknown_name = "Unknown quantity unit"
        low_name = "Low confidence item"
        package_name = "Piece without package"
        suspicious_name = "Suspicious normalized price"
        self.add_item(unknown_name, quantity_unit="unknown")
        self.add_item(low_name, confidence=0.4)
        self.add_item(package_name, quantity_unit="piece", package_size=None)
        self.add_item(suspicious_name, normalized_unit_price=10001)

        cases = (
            ("unknown", unknown_name, low_name),
            ("low_confidence", low_name, package_name),
            ("missing_package", package_name, suspicious_name),
            ("suspicious", suspicious_name, unknown_name),
        )
        for issue_filter, included, excluded in cases:
            with self.subTest(issue_filter=issue_filter):
                html = self.client.get(
                    f"/data-quality/prices?filter={issue_filter}&limit=25"
                ).get_data(as_text=True)
                self.assertIn(included, html)
                self.assertNotIn(excluded, html)
                self.assertIn(
                    f'class="problem-selector-option is-active"\n                href="/data-quality/prices?filter={issue_filter}&amp;limit=25"\n                aria-current="page"',
                    html,
                )

    def test_primary_diagnostic_information_precedes_technical_metadata(self):
        self.add_item(
            "Primary product identity",
            quantity_unit="unknown",
            normalized_unit_price=None,
            normalized_price_unit="unknown",
        )
        html = self.client.get("/data-quality/prices?filter=unknown").get_data(as_text=True)

        product_index = html.index('class="diagnostic-product"')
        problem_index = html.index('class="diagnostic-problem"')
        technical_index = html.index('class="diagnostic-technical"')
        self.assertLess(product_index, problem_index)
        self.assertLess(problem_index, technical_index)
        self.assertIn("Неизвестная единица", html)
        self.assertIn("Единица количества не определена", html)

    def test_empty_dataset_and_filtered_no_results_are_distinct(self):
        empty_html = self.client.get("/data-quality/prices").get_data(as_text=True)
        self.assertIn("Пока нечего проверять", empty_html)
        self.assertIn("Недостаточно данных", empty_html)
        self.assertNotIn('class="diagnostic-register"', empty_html)

        self.add_item("Healthy normalized item")
        filtered_html = self.client.get(
            "/data-quality/prices?filter=suspicious"
        ).get_data(as_text=True)
        self.assertIn("В этом типе проблем строк не найдено", filtered_html)
        self.assertIn('href="/data-quality/prices?limit=50"', filtered_html)
        self.assertNotIn('class="diagnostic-register"', filtered_html)

    def test_problem_selector_preserves_existing_filter_values_and_limit(self):
        html = self.client.get(
            "/data-quality/prices?filter=low_confidence&limit=100"
        ).get_data(as_text=True)

        for value in ("all", "unknown", "low_confidence", "missing_package", "suspicious"):
            self.assertIn(f"filter={value}&amp;limit=100", html)
        self.assertIn('name="filter" value="low_confidence"', html)
        self.assertIn('<option value="100" selected', html)
        self.assertIn("Сбросить фильтр", html)

    def test_price_quality_styles_are_scoped_and_responsive(self):
        css = (
            Path(__file__).parents[1] / "app" / "web" / "static" / "style.css"
        ).read_text(encoding="utf-8")

        for contract in (
            ".price-quality-workspace",
            ".coverage-band",
            ".problem-selector-option.is-active",
            ".diagnostic-register",
            ".diagnostic-row .diagnostic-product",
            "@media (max-width: 390px)",
            "@media (prefers-reduced-motion: reduce)",
        ):
            self.assertIn(contract, css)


    def test_all_problems_reports_arithmetic_conflict_despite_high_confidence(self):
        self.add_item(
            "Persisted arithmetic conflict",
            quantity=2,
            line_total=3.10,
            unit_price=1.99,
            confidence=0.95,
        )

        html = self.client.get("/data-quality/prices?filter=all").get_data(as_text=True)

        self.assertIn("Persisted arithmetic conflict", html)
        self.assertIn("Арифметика цены расходится", html)
        self.assertIn("Уверенность нормализации", html)


if __name__ == "__main__":
    unittest.main()
