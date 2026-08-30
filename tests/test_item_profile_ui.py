import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

import app.db as db
from app.web.app import create_app


class ItemProfileWorkspaceTests(unittest.TestCase):
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

    def add_purchase(
        self,
        product_name,
        *,
        alias=None,
        date="2026-06-01",
        store="TEST STORE",
        price=2.5,
        normalized_price=2.5,
        normalized_unit="eur_per_piece",
        category="прочее",
        package_size=1,
        package_unit="piece",
        price_source="package_name",
        price_confidence=0.95,
    ):
        with db.get_connection() as conn:
            receipt_number = f"item-profile-{conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]}"
            receipt = conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, ?, ?, ?)",
                (date, store, price, receipt_number),
            )
            receipt_id = receipt.lastrowid
            item = conn.execute(
                """
                INSERT INTO items (
                    receipt_id, name, canonical_name, normalized_name,
                    quantity, price, line_total, unit_price,
                    quantity_unit, package_size, package_unit,
                    normalized_unit_price, normalized_price_unit,
                    price_parse_source, price_parse_confidence, category, category_source
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, 'piece', ?, ?, ?, ?, ?, ?, ?, 'manual')
                """,
                (
                    receipt_id,
                    alias or product_name,
                    product_name,
                    product_name.lower(),
                    price,
                    price,
                    price,
                    package_size,
                    package_unit,
                    normalized_price,
                    normalized_unit,
                    price_source,
                    price_confidence,
                    category,
                ),
            )
            conn.commit()
        return receipt_id, item.lastrowid

    def item_url(self, name):
        return f"/item/{quote(name, safe='')}"

    def test_product_dossier_has_one_heading_summary_story_and_register(self):
        product = "Очень длинное название товара для проверки переноса 4x125g"
        receipt_ids = []
        for index, (date, store, price) in enumerate(
            (
                ("2026-05-03", "RIMI", 2.20),
                ("2026-06-07", "MAXIMA", 2.50),
                ("2026-07-11", "RIMI", 2.75),
            )
        ):
            receipt_id, _ = self.add_purchase(
                product,
                alias=f"Raw product name {index}",
                date=date,
                store=store,
                price=price,
                normalized_price=price,
                category="напитки",
            )
            receipt_ids.append(receipt_id)

        response = self.client.get(self.item_url(product))
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="product-dossier"', html)
        self.assertIn('class="product-summary"', html)
        self.assertIn('class="product-price-story"', html)
        self.assertIn('data-trend-url="/analytics/item_trend?item=', html)
        self.assertIn("%D0%9E%D1%87%D0%B5%D0%BD%D1%8C", html)
        self.assertIn('class="purchase-register"', html)
        self.assertEqual(html.count("data-purchase-record"), 3)
        self.assertIn("3 появлений", html)
        self.assertIn("3 записей", html)
        self.assertIn("напитки", html)
        self.assertIn("Недостаточно истории цен", html)
        self.assertIn("Сопоставимых наблюдений: 2 из 3.", html)
        for receipt_id in receipt_ids:
            self.assertIn(f'href="/receipt/{receipt_id}"', html)
        self.assertNotIn('class="metric-card"', html)
        self.assertNotIn('class="app-table', html)

    def test_category_editing_keeps_existing_routes_and_scope(self):
        product = "Category form product"
        _, item_id = self.add_purchase(product, category="овощи и фрукты")
        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn(f'action="/item/{item_id}/category"', html)
        self.assertIn('name="category"', html)
        self.assertIn('name="category_scope"', html)
        self.assertIn('<option value="product" selected>Всему товару</option>', html)
        self.assertIn('<option value="item">Только этой позиции</option>', html)
        self.assertIn('value="овощи и фрукты" selected', html)

    def test_legacy_review_category_is_visible_and_editable_as_unresolved(self):
        product = "Legacy review product"
        self.add_purchase(product, category="мясо")

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Сохранено ранее: мясо", html)
        self.assertIn('value="прочее / требует решения" selected', html)
        self.assertNotIn('<option value="мясо"', html)

    def test_short_history_is_explained_without_visible_empty_chart(self):
        product = "Single purchase product"
        self.add_purchase(product, normalized_price=None, normalized_unit="unknown")
        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Цена пока несопоставима", html)
        self.assertIn("Не удалось надёжно определить цену за кг, литр или штуку.", html)
        self.assertNotIn("Сопоставимых наблюдений:", html)
        self.assertIn('data-trend-canvas hidden', html)
        self.assertIn("для динамики нужен ещё один период", (
            Path(__file__).parents[1] / "app" / "web" / "static" / "item-profile.js"
        ).read_text(encoding="utf-8"))
        self.assertIn('class="purchase-register"', html)

    def test_price_story_does_not_fall_back_to_legacy_price(self):
        product = "Legacy-only dossier product"
        for index, price in enumerate((1.0, 1.0, 2.0, 4.0), start=1):
            self.add_purchase(
                product,
                date=f"2026-07-{index:02d}",
                price=price,
                normalized_price=None,
                normalized_unit="unknown",
            )

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Цена пока несопоставима", html)
        self.assertNotIn("Сопоставимых наблюдений:", html)
        self.assertNotIn("Дороже обычного", html)

    def test_price_story_explains_uncertain_identity(self):
        product = "Dilles 100g"
        self.add_purchase(product)

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("История товара требует уточнения", html)
        self.assertIn("Покупки пока нельзя надёжно объединить в одну историю цен.", html)
        self.assertNotIn("Сопоставимых наблюдений:", html)

    def test_price_story_explains_evidence_review_without_progress(self):
        product = "Review evidence product 1L"
        _, item_id = self.add_purchase(product, price=2.5, normalized_price=2.5)
        with db.get_connection() as conn:
            conn.execute("UPDATE items SET unit_price = 1 WHERE id = ?", (item_id,))
            conn.commit()

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Данные требуют проверки", html)
        self.assertIn("Эту покупку пока нельзя безопасно использовать для сравнения цен.", html)
        self.assertNotIn("Сопоставимых наблюдений:", html)

    def test_price_story_success_state_keeps_label_and_percentage(self):
        product = "Successful deviation product 1L"
        for index, price in enumerate((2.0, 2.0, 2.0, 2.3), start=1):
            self.add_purchase(
                product,
                date=f"2026-07-{index:02d}",
                price=price,
                normalized_price=price,
                normalized_unit="eur_per_l",
                package_size=1000,
                package_unit="ml",
            )

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Дороже обычного", html)
        self.assertIn("+15.0%", html)

    def test_missing_product_has_distinct_empty_state(self):
        html = self.client.get(self.item_url("Missing product")).get_data(as_text=True)

        self.assertIn("История товара пока пуста", html)
        self.assertIn("В базе нет покупок", html)
        self.assertNotIn('class="product-summary"', html)
        self.assertNotIn('class="purchase-register"', html)
        self.assertNotIn('data-product-trend', html)

    def test_item_profile_assets_follow_theme_and_chart_lifecycle(self):
        script = (
            Path(__file__).parents[1] / "app" / "web" / "static" / "item-profile.js"
        ).read_text(encoding="utf-8")

        for contract in (
            "Chart.getChart(canvas)",
            "chart.destroy()",
            "Chart.defaults.color = colors.text",
            "Chart.defaults.borderColor = colors.line",
            "receipt-intelligence:themechange",
            "prefers-reduced-motion: reduce",
            "points.length < 2",
        ):
            self.assertIn(contract, script)
        self.assertEqual(script.count("new Chart("), 1)

    def test_item_profile_styles_are_scoped_and_responsive(self):
        css = (
            Path(__file__).parents[1] / "app" / "web" / "static" / "style.css"
        ).read_text(encoding="utf-8")

        for contract in (
            ".item-profile-page .app-container",
            ".product-dossier-header",
            ".product-summary",
            ".product-price-story",
            ".purchase-register",
            ".product-related-grid",
            "@media (max-width: 820px)",
            "@media (max-width: 560px)",
            "@media (prefers-reduced-motion: reduce)",
        ):
            self.assertIn(contract, css)


    def test_product_dossier_uses_price_model_semantic_labels(self):
        product = "Semantic labels product 500g"
        self.add_purchase(product, price=3.10, normalized_price=6.20, package_size=500, package_unit="g")
        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        for label in (
            "Итого за позицию",
            "Оплачено на единицу записанного количества",
            "Размер упаковки",
            "Сопоставимая цена",
            "Источник нормализации",
            "Уверенность нормализации",
        ):
            self.assertIn(label, html)
        self.assertNotIn("Цена упаковки", html)
        self.assertNotIn("Цена за строку", html)

    def test_store_comparison_renders_comparable_medians_and_historical_claim(self):
        product = "Comparable store product 500g"
        for store, prices in (("MAXIMA", (5.0, 6.0, 7.0)), ("RIMI", (8.0, 9.0, 10.0))):
            for index, price in enumerate(prices, start=1):
                self.add_purchase(
                    product,
                    store=store,
                    date=f"2026-0{index}-01",
                    price=price / 2,
                    normalized_price=price,
                    normalized_unit="eur_per_kg",
                    package_size=500,
                    package_unit="g",
                )

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Где вы платили меньше", html)
        self.assertIn("Сопоставимая история", html)
        self.assertIn("6.00", html)
        self.assertIn("9.00", html)
        self.assertIn("€/kg", html)
        self.assertIn("MAXIMA", html)
        self.assertIn("примерно на 33,3% ниже", html)
        self.assertIn("не текущие цены", html)

    def test_store_comparison_renders_preliminary_without_cheaper_store_claim(self):
        product = "Preliminary store product 500g"
        self.add_purchase(product, store="MAXIMA", normalized_price=5.0, package_size=500, package_unit="g")
        self.add_purchase(product, store="RIMI", normalized_price=7.0, package_size=500, package_unit="g")

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Сравнение пока предварительное", html)
        self.assertIn("Недостаточно истории, чтобы определить", html)
        self.assertNotIn("примерно на", html)

    def test_store_comparison_renders_one_store_as_normal_limitation(self):
        product = "One store product 500g"
        for price in (5.0, 6.0, 7.0):
            self.add_purchase(product, store="MAXIMA", normalized_price=price, package_size=500, package_unit="g")

        html = self.client.get(self.item_url(product)).get_data(as_text=True)

        self.assertIn("Сравнение по магазинам пока недоступно", html)
        self.assertIn("только в одном магазине", html)
        self.assertNotIn("store-comparison-row", html)


if __name__ == "__main__":
    unittest.main()
