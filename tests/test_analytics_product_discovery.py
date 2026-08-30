import tempfile
import unittest
from pathlib import Path

import app.db as db
from app.analytics_service import get_analytics_data
from app.web.app import create_app


class AnalyticsProductDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "analytics-discovery.db"
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_purchase(self, name, *, canonical_name=None, price=1.0, index=0):
        with db.get_connection() as conn:
            receipt = conn.execute(
                """
                INSERT INTO receipts (date, store, total, receipt_number)
                VALUES (?, ?, ?, ?)
                """,
                ("2026-08-01", "TEST STORE", price, f"discovery-{index}-{name}"),
            )
            conn.execute(
                """
                INSERT INTO items (
                    receipt_id, name, canonical_name, normalized_name,
                    quantity, price, category
                ) VALUES (?, ?, ?, ?, 1, ?, 'прочее')
                """,
                (receipt.lastrowid, name, canonical_name, name.casefold(), price),
            )
            conn.commit()

    def search(self, query):
        response = self.client.get(
            "/autocomplete/item_names",
            query_string={"q": query, "details": "1"},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_product_outside_top_ten_is_discoverable(self):
        for index in range(10):
            self.add_purchase(
                f"Top product {index}",
                price=100 - index,
                index=index,
            )
        self.add_purchase("Outside top ten product", price=0.5, index=20)

        self.assertNotIn(
            "Outside top ten product",
            get_analytics_data()["top"]["labels"],
        )
        self.assertEqual(
            self.search("outside"),
            [{
                "name": "Outside top ten product",
                "profile_url": "/item/Outside%20top%20ten%20product",
            }],
        )

    def test_canonical_aliases_resolve_to_one_effective_identity(self):
        self.add_purchase("Raw alias one", canonical_name="Shared canonical", index=1)
        self.add_purchase("Raw alias two", canonical_name="Shared canonical", index=2)

        self.assertEqual(
            self.search("raw alias"),
            [{
                "name": "Shared canonical",
                "profile_url": "/item/Shared%20canonical",
            }],
        )

    def test_null_canonical_name_falls_back_to_raw_name(self):
        self.add_purchase("Fallback raw identity", index=1)

        self.assertEqual(
            self.search("fallback"),
            [{
                "name": "Fallback raw identity",
                "profile_url": "/item/Fallback%20raw%20identity",
            }],
        )

    def test_invalid_free_text_never_receives_profile_url(self):
        self.add_purchase("Known product", index=1)

        self.assertEqual(self.search("not a persisted identity"), [])

    def test_url_sensitive_effective_identity_opens_existing_dossier(self):
        product = "Kefīrs / lauku 2% + BIO!"
        self.add_purchase(product, index=1)

        result = self.search("kefīrs")[0]
        self.assertEqual(result["name"], product)
        self.assertIn("%25", result["profile_url"])

        response = self.client.get(result["profile_url"])
        self.assertEqual(response.status_code, 200)
        self.assertIn(product, response.get_data(as_text=True))

    def test_analytics_renders_discovery_copy_and_inactive_actions(self):
        html = self.client.get("/analytics").get_data(as_text=True)

        self.assertIn("Исследовать конкретный товар", html)
        self.assertIn(
            "Найдите товар, чтобы посмотреть его историю цен и подробный профиль.",
            html,
        )
        self.assertIn('id="researchTrendButton"', html)
        self.assertIn('id="researchProfileLink"', html)
        self.assertIn("Показать динамику", html)
        self.assertIn("Открыть профиль товара", html)
        self.assertIn('id="researchTrendButton" class="btn btn-outline-primary" type="submit" disabled', html)
        self.assertIn('id="researchProfileLink"', html)
        self.assertIn("hidden", html)

    def test_legacy_autocomplete_response_remains_name_list(self):
        self.add_purchase("Legacy autocomplete product", index=1)

        response = self.client.get(
            "/autocomplete/item_names",
            query_string={"q": "legacy"},
        )

        self.assertEqual(response.get_json(), ["Legacy autocomplete product"])


if __name__ == "__main__":
    unittest.main()
