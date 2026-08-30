import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.category_keywords import categorize_with_source, normalize_category_name
from app.category_rules import get_category_rule, upsert_category_rule
from app.product_normalizer import normalize_product_name
from app.web.app import create_app


class CategoryEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.create_tables()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_receipt(self):
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES ('2026-01-01', 'TEST', 0, ?)",
                (f"r-{id(self)}",),
            )
            conn.commit()
            return conn.execute("SELECT id FROM receipts ORDER BY id DESC LIMIT 1").fetchone()[0]

    def add_item(self, receipt_id, name, category="прочее", source="fallback", canonical_name=None):
        normalized = normalize_product_name(name)
        with db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO items (receipt_id, name, normalized_name, canonical_name, quantity, price, category, category_source)
                VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (receipt_id, name, normalized, canonical_name, category, source),
            )
            conn.commit()
            return conn.execute("SELECT id FROM items ORDER BY id DESC LIMIT 1").fetchone()[0]

    def test_normalize_category_name(self):
        self.assertEqual(normalize_category_name("молочка"), "молочные продукты и альтернативы")
        self.assertEqual(normalize_category_name("кот"), "товары для животных")
        self.assertEqual(normalize_category_name(None), "прочее / требует решения")

    def test_categorize_with_source(self):
        self.assertEqual(
            categorize_with_source("piens 2%"),
            ("молочные продукты и альтернативы", "rule"),
        )
        self.assertEqual(
            categorize_with_source("xyz unknown thing"),
            ("прочее / требует решения", "fallback"),
        )

    def test_manual_rule_update_and_inherited_import(self):
        with db.get_connection() as conn:
            key = normalize_product_name("Coca Cola Zero 1L")
            upsert_category_rule(conn, key, "напитки")
            upsert_category_rule(conn, key, "сладости")
            conn.commit()

        self.assertTrue(db.add_receipt_with_items(
            "2026-01-02",
            "TEST",
            1,
            "new-import",
            [{"name": "Coca Cola Zero 1L", "quantity": 1, "price": 1}],
        ))

        with db.get_connection() as conn:
            row = conn.execute("SELECT category, category_source FROM items").fetchone()
            rule = get_category_rule(conn, key)

        self.assertEqual(rule["category"], "снеки и сладости")
        self.assertEqual(row, ("снеки и сладости", "inherited"))

    def test_exact_rule_remains_authoritative_over_classifier_disagreement(self):
        name = "Alus TEST 5,0% 0,5L"
        key = normalize_product_name(name)
        with db.get_connection() as conn:
            upsert_category_rule(conn, key, "безалкогольные напитки")
            conn.commit()

        self.assertEqual(categorize_with_source(name)[0], "алкоголь")
        self.assertTrue(db.add_receipt_with_items(
            "2026-01-03",
            "TEST",
            1,
            "rule-over-classifier",
            [{"name": name, "quantity": 1, "price": 1}],
        ))

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT category, category_source FROM items WHERE name = ?",
                (name,),
            ).fetchone()

        self.assertEqual(row, ("безалкогольные напитки", "inherited"))

    def test_unseen_import_uses_classifier_and_fails_closed(self):
        items = [
            {"name": "Olas brīvos apstākļos 10gab", "quantity": 1, "price": 2},
            {"name": "Tomātu pasta TEST 500g", "quantity": 1, "price": 2},
            {"name": "Instant nūdeles TEST 90g", "quantity": 1, "price": 2},
            {"name": "Santa Maria 250g", "quantity": 1, "price": 2},
        ]

        self.assertTrue(db.add_receipt_with_items(
            "2026-01-04", "TEST", 8, "unseen-classifier", items
        ))

        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT name, category, category_source FROM items ORDER BY id"
            ).fetchall()

        self.assertEqual(rows, [
            ("Olas brīvos apstākļos 10gab", "яйца", "rule"),
            ("Tomātu pasta TEST 500g", "соусы, приправы и консервы", "rule"),
            ("Instant nūdeles TEST 90g", "готовая еда и быстрое приготовление", "rule"),
            ("Santa Maria 250g", "прочее / требует решения", "fallback"),
        ])

    def test_scope_item_updates_one_without_rule(self):
        receipt_id = self.add_receipt()
        first_id = self.add_item(receipt_id, "Blue Moon 0.33L")
        self.add_item(receipt_id, "Blue Moon 0.33L")

        app = create_app()
        client = app.test_client()
        response = client.post(
            f"/item/{first_id}/category",
            data={"category": "напитки", "category_scope": "item"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        with db.get_connection() as conn:
            rows = conn.execute("SELECT category, category_source FROM items ORDER BY id").fetchall()
            rules = conn.execute("SELECT COUNT(*) FROM product_category_rules").fetchone()[0]

        self.assertEqual(rows[0], ("безалкогольные напитки", "manual"))
        self.assertEqual(rows[1], ("прочее", "fallback"))
        self.assertEqual(rules, 0)

    def test_scope_product_updates_exact_group_only(self):
        receipt_id = self.add_receipt()
        first_id = self.add_item(receipt_id, "Blue Moon 0.33L")
        self.add_item(receipt_id, "Blue Moon 0.33L")
        self.add_item(receipt_id, "Blue Moon 0.5L")

        app = create_app()
        client = app.test_client()
        response = client.post(
            f"/item/{first_id}/category",
            data={"category": "напитки", "category_scope": "product"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        with db.get_connection() as conn:
            rows = conn.execute("SELECT name, category, category_source FROM items ORDER BY id").fetchall()
            rules = conn.execute("SELECT COUNT(*) FROM product_category_rules").fetchone()[0]

        self.assertEqual(rows[0][1:], ("безалкогольные напитки", "manual"))
        self.assertEqual(rows[1][1:], ("безалкогольные напитки", "manual"))
        self.assertEqual(rows[2][1:], ("прочее", "fallback"))
        self.assertEqual(rules, 1)

    def test_category_post_rejects_noncanonical_value(self):
        receipt_id = self.add_receipt()
        item_id = self.add_item(receipt_id, "Invalid category product")
        client = create_app().test_client()

        response = client.post(
            f"/item/{item_id}/category",
            data={"category": "arbitrary category", "category_scope": "item"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        with db.get_connection() as conn:
            self.assertEqual(
                conn.execute("SELECT category, category_source FROM items WHERE id = ?", (item_id,)).fetchone(),
                ("прочее", "fallback"),
            )

    def test_review_route_filters(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id, "Review Item 500g", category="прочее", source="fallback")

        app = create_app()
        client = app.test_client()
        response = client.get("/products/review?filter=other&sort=count&limit=25")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Review Item 500g".encode(), response.data)

    def test_review_route_renders_decision_workspace(self):
        receipt_id = self.add_receipt()
        self.add_item(
            receipt_id,
            "Очень длинное название товара для проверки переноса без потери исходного текста 500g",
            category="прочее",
            source="fallback",
        )

        app = create_app()
        client = app.test_client()
        response = client.get("/products/review")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="review-workspace"', html)
        self.assertIn('class="review-summary-band"', html)
        self.assertIn('class="review-queue"', html)
        self.assertIn('data-review-item', html)
        self.assertIn('aria-label="Причины проверки"', html)
        self.assertIn('action="/products/review/category"', html)
        self.assertIn('href="/item/', html)
        self.assertIn(f'href="/receipt/{receipt_id}"', html)
        self.assertIn("Категория для подтверждения", html)
        self.assertIn("Уверенность не рассчитывается", html)
        self.assertNotIn('class="metric-card"', html)
        self.assertNotIn('class="surface review-card"', html)

    def test_review_route_renders_completed_empty_state(self):
        app = create_app()
        client = app.test_client()
        response = client.get("/products/review")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="review-empty-state"', html)
        self.assertIn("Все товары проверены", html)
        self.assertNotIn("Нет товаров для проверки", html)

    def test_suggestions_route_renders_comparison_workspace(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id, "GRIMBERGEN Blonde 6,7% 0,5L", category="напитки")
        self.add_item(receipt_id, "GRIMBERGEN Blonde 6.7% 500 ml", category="напитки")

        app = create_app()
        client = app.test_client()
        response = client.get("/products/suggestions?q=GRIMBERGEN&confidence=high&limit=25")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="comparison-workspace"', html)
        self.assertIn("comparison-summary-band", html)
        self.assertIn('class="comparison-queue"', html)
        self.assertIn('data-comparison-pair', html)
        self.assertEqual(html.count('data-comparison-confidence'), 1)
        self.assertIn('data-comparison-side="a"', html)
        self.assertIn('data-comparison-side="b"', html)
        self.assertIn("GRIMBERGEN Blonde 6,7% 0,5L", html)
        self.assertIn("GRIMBERGEN Blonde 6.7% 500 ml", html)
        self.assertIn("похожесть названия", html)
        self.assertIn("совпадает объем 500 ml", html)
        self.assertIn("категории совпадают", html)
        self.assertIn('href="/products/merge?q=', html)
        self.assertEqual(html.count('type="button" data-dismiss-pair'), 1)

        first_side = html.index('data-comparison-side="a"')
        mobile_relation = html.index('class="comparison-mobile-relation"')
        second_side = html.index('data-comparison-side="b"')
        self.assertLess(first_side, mobile_relation)
        self.assertLess(mobile_relation, second_side)

    def test_suggestions_route_distinguishes_empty_queue_from_filtered_no_results(self):
        app = create_app()
        client = app.test_client()

        empty_html = client.get("/products/suggestions").get_data(as_text=True)
        filtered_html = client.get(
            "/products/suggestions?q=definitely-not-a-product&confidence=high"
        ).get_data(as_text=True)

        self.assertIn('class="comparison-empty-state"', empty_html)
        self.assertIn("Подозрительных пар сейчас нет", empty_html)
        self.assertIn("По текущему фильтру пары не найдены", filtered_html)
        self.assertIn('href="/products/suggestions"', filtered_html)

    def test_merge_route_renders_bulk_selection_workspace(self):
        receipt_id = self.add_receipt()
        product_name = "Очень длинное исходное название товара для проверки устойчивого переноса 750 ml"
        self.add_item(receipt_id, product_name, category="напитки")
        self.add_item(receipt_id, product_name, category="напитки")

        app = create_app()
        client = app.test_client()
        response = client.get("/products/merge?q=Очень")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn('class="merge-workspace"', html)
        self.assertIn('class="review-toolbar merge-toolbar"', html)
        self.assertIn('data-selection-table', html)
        self.assertIn('data-selection-row', html)
        self.assertIn('data-selected-state', html)
        self.assertIn('name="selected_names"', html)
        self.assertIn('data-selected-count', html)
        self.assertIn('data-affected-rows', html)
        self.assertIn('data-affected-receipts', html)
        self.assertIn('data-selected-list', html)
        self.assertIn('class="merge-command-band"', html)
        self.assertIn('name="canonical_name"', html)
        self.assertIn('autocomplete="off"\n                required', html)
        self.assertIn('aria-describedby="canonical-name-help canonical-name-error"', html)
        self.assertIn('data-reset-selection', html)
        self.assertIn(product_name, html)
        self.assertIn('src="/static/product-merge.js"', html)
        self.assertNotIn("novalidate", html)
        self.assertNotIn('class="metric-card"', html)

    def test_merge_route_distinguishes_empty_search_results(self):
        app = create_app()
        client = app.test_client()

        empty_html = client.get("/products/merge").get_data(as_text=True)
        no_results_html = client.get(
            "/products/merge?q=definitely-not-a-product"
        ).get_data(as_text=True)

        self.assertIn("Список товаров пока пуст", empty_html)
        self.assertIn("По текущему поиску товары не найдены", no_results_html)
        self.assertIn('href="/products/merge"', no_results_html)

    def test_merge_post_keeps_existing_merge_semantics(self):
        receipt_id = self.add_receipt()
        self.add_item(receipt_id, "Merge Source A")
        self.add_item(receipt_id, "Merge Source B")

        app = create_app()
        client = app.test_client()
        response = client.post(
            "/products/merge",
            data={
                "selected_names": ["Merge Source A", "Merge Source B"],
                "canonical_name": "Canonical Result",
                "q": "Merge Source",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("q=Merge+Source", response.headers["Location"])
        with db.get_connection() as conn:
            names = conn.execute(
                "SELECT DISTINCT canonical_name FROM items ORDER BY canonical_name"
            ).fetchall()
        self.assertEqual(names, [("Canonical Result",)])


if __name__ == "__main__":
    unittest.main()
