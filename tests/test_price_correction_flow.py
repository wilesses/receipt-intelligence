import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

import app.db as db
from app.price_deviation import evaluate_price_deviation, is_eligible_price_observation
from app.store_price_comparison import build_store_price_comparison
from app.web.app import create_app


class PriceCorrectionFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.create_tables()
        self.item_id, self.receipt_id = self.add_item("Jogurts 400g")
        self.other_item_id, _ = self.add_item("Cits produkts 250g")
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="price-correction-test")
        self.client = self.app.test_client()

    def tearDown(self):
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def add_item(self, name, **overrides):
        values = {
            "quantity": 2.0,
            "price": 4.0,
            "line_total": 4.0,
            "unit_price": 2.0,
            "quantity_unit": "piece",
            "package_size": None,
            "package_unit": "unknown",
            "normalized_unit_price": 2.0,
            "normalized_price_unit": "eur_per_piece",
            "price_parse_source": "inferred_piece",
            "price_parse_confidence": 0.70,
        }
        values.update(overrides)
        with db.get_connection() as conn:
            number = f"correction-{conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]}"
            receipt = conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES ('2026-08-23', 'TEST', ?, ?)",
                (values["line_total"] or 0, number),
            )
            receipt_id = receipt.lastrowid
            item = conn.execute(
                """
                INSERT INTO items (
                    receipt_id, name, normalized_name, canonical_name, quantity,
                    price, line_total, unit_price, quantity_unit, package_size,
                    package_unit, normalized_unit_price, normalized_price_unit,
                    price_parse_source, price_parse_confidence, category, category_source
                ) VALUES (?, ?, ?, 'Йогурт', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'молочные продукты и альтернативы', 'manual')
                """,
                (
                    receipt_id,
                    name,
                    name.casefold(),
                    values["quantity"],
                    values["price"],
                    values["line_total"],
                    values["unit_price"],
                    values["quantity_unit"],
                    values["package_size"],
                    values["package_unit"],
                    values["normalized_unit_price"],
                    values["normalized_price_unit"],
                    values["price_parse_source"],
                    values["price_parse_confidence"],
                ),
            )
            conn.commit()
            return item.lastrowid, receipt_id

    def item_row(self, item_id):
        with db.get_connection() as conn:
            conn.row_factory = db.sqlite3.Row
            return dict(conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone())

    def preview(self):
        return self.client.post(
            f"/data-quality/prices/{self.item_id}/correct?filter=missing_package&limit=25",
            data={
                "action": "preview",
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

    @staticmethod
    def preview_token(response):
        match = re.search(r'name="preview_token" value="([^"]+)"', response.get_data(as_text=True))
        if not match:
            raise AssertionError("preview token missing")
        return match.group(1)

    def test_get_shows_structured_controls_and_source_receipt(self):
        response = self.client.get(
            f"/data-quality/prices/{self.item_id}/correct?filter=missing_package&limit=25"
        )
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Jogurts 400g", html)
        self.assertIn(f'href="/receipt/{self.receipt_id}"', html)
        self.assertIn('name="quantity_unit"', html)
        self.assertIn('name="package_size"', html)
        self.assertIn('name="package_unit"', html)
        self.assertIn("Предпросмотр", html)
        self.assertNotIn("Применить исправление", html)

    def test_preview_does_not_write_database(self):
        before = self.item_row(self.item_id)

        response = self.preview()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.item_row(self.item_id), before)
        self.assertIn("После исправления", response.get_data(as_text=True))
        self.assertIn("Применить исправление", response.get_data(as_text=True))

    def test_apply_updates_one_row_and_preserves_raw_evidence(self):
        target_before = self.item_row(self.item_id)
        other_before = self.item_row(self.other_item_id)
        preview = self.preview()
        token = self.preview_token(preview)

        response = self.client.post(
            f"/data-quality/prices/{self.item_id}/correct?filter=missing_package&limit=25",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/data-quality/prices?filter=missing_package&limit=25", response.headers["Location"])
        after = self.item_row(self.item_id)
        for field in (
            "id", "receipt_id", "name", "normalized_name", "canonical_name",
            "category", "category_source", "quantity", "price", "line_total",
        ):
            self.assertEqual(after[field], target_before[field], field)
        self.assertEqual(after["package_size"], 400)
        self.assertEqual(after["package_unit"], "g")
        self.assertEqual(after["normalized_unit_price"], 5.0)
        self.assertEqual(after["normalized_price_unit"], "eur_per_kg")
        self.assertEqual(after["price_parse_source"], "manual_correction")
        self.assertEqual(after["price_parse_confidence"], 0.85)
        self.assertEqual(self.item_row(self.other_item_id), other_before)

    def test_apply_rejects_stale_before_state(self):
        preview = self.preview()
        token = self.preview_token(preview)
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE items SET price_parse_confidence = 0.65 WHERE id = ?",
                (self.item_id,),
            )
            conn.commit()

        response = self.client.post(
            f"/data-quality/prices/{self.item_id}/correct",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Данные изменились", response.get_data(as_text=True))
        after = self.item_row(self.item_id)
        self.assertEqual(after["price_parse_confidence"], 0.65)
        self.assertEqual(after["price_parse_source"], "inferred_piece")

    def test_apply_rejects_proposal_different_from_preview(self):
        token = self.preview_token(self.preview())

        response = self.client.post(
            f"/data-quality/prices/{self.item_id}/correct",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "500",
                "package_unit": "g",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.item_row(self.item_id)["package_size"], None)



    def test_queue_exposes_only_correctable_action_and_explains_blocked_row(self):
        blocked_id, _ = self.add_item(
            "Требуется исходный чек",
            line_total=None,
            normalized_unit_price=None,
            normalized_price_unit="unknown",
            price_parse_source="unresolved",
            price_parse_confidence=None,
        )

        response = self.client.get("/data-quality/prices?filter=all&limit=50")
        html = response.get_data(as_text=True)

        self.assertIn(
            f'href="/data-quality/prices/{self.item_id}/correct?filter=all&amp;limit=50"',
            html,
        )
        self.assertIn("Исправить evidence", html)
        self.assertIsNotNone(re.search(
            r'class="diagnostic-technical"[^>]*>(?:(?!</td>).)*Исправить evidence(?:(?!</td>).)*</td>',
            html,
            re.DOTALL,
        ))
        self.assertIn("Требуется исходный чек", html)
        self.assertIn("Итог строки требует проверки исходного чека", html)
        self.assertNotIn(
            f'href="/data-quality/prices/{blocked_id}/correct?filter=all&amp;limit=50"',
            html,
        )

    def test_successful_apply_recalculates_missing_package_queue(self):
        token = self.preview_token(self.preview())
        self.client.post(
            f"/data-quality/prices/{self.item_id}/correct?filter=missing_package&limit=25",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

        html = self.client.get(
            "/data-quality/prices?filter=missing_package&limit=25"
        ).get_data(as_text=True)

        self.assertNotIn("Jogurts 400g", html)

    def test_downstream_consumers_read_manual_correction_without_push_updates(self):
        identity = "Corrected yogurt"
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE items SET canonical_name = ? WHERE id = ?",
                (identity, self.item_id),
            )
            conn.commit()
        token = self.preview_token(self.preview())
        self.client.post(
            f"/data-quality/prices/{self.item_id}/correct",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

        receipt_html = self.client.get(f"/receipt/{self.receipt_id}").get_data(as_text=True)
        dossier_html = self.client.get(f"/item/{quote(identity)}").get_data(as_text=True)
        trend = self.client.get(f"/analytics/item_trend?item={quote(identity)}").get_json()
        self.assertIn("Проверено", receipt_html)
        self.assertIn("5.00", dossier_html)
        self.assertIn("Ручная structured correction", dossier_html)
        self.assertEqual(trend["status"], "ready")
        self.assertEqual(trend["values"], [5.0])
        self.assertEqual(trend["normalized_price_unit"], "eur_per_kg")

        with db.get_connection() as conn:
            conn.row_factory = db.sqlite3.Row
            current = dict(conn.execute(
                """
                SELECT items.*, receipts.store, receipts.date
                FROM items JOIN receipts ON receipts.id = items.receipt_id
                WHERE items.id = ?
                """,
                (self.item_id,),
            ).fetchone())
        self.assertTrue(is_eligible_price_observation(current))

        priors = []
        for offset, normalized in enumerate((4.5, 5.0, 5.5), start=1):
            prior = dict(current)
            prior.update({
                "id": 100 + offset,
                "receipt_id": 100 + offset,
                "date": f"2026-07-0{offset}",
                "normalized_unit_price": normalized,
                "price_parse_source": "package_name",
            })
            priors.append(prior)
        deviation = evaluate_price_deviation(current, [*priors, current])
        self.assertEqual(deviation["status"], "NORMAL")
        self.assertEqual(deviation["eligible_prior_observation_count"], 3)

        other_store = dict(current)
        other_store.update({
            "id": 200,
            "receipt_id": 200,
            "store": "OTHER",
            "date": "2026-08-20",
            "price_parse_source": "package_name",
        })
        comparison = build_store_price_comparison([current, other_store])
        self.assertEqual(comparison["evidence_level"], "PRELIMINARY")
        self.assertEqual({store["store"] for store in comparison["stores"]}, {"TEST", "OTHER"})


    def test_correction_workspace_has_scoped_responsive_styles(self):
        css = (
            Path(__file__).parents[1]
            / "app"
            / "web"
            / "static"
            / "style.css"
        ).read_text(encoding="utf-8")

        for contract in (
            ".price-correction-workspace",
            ".correction-evidence-grid",
            ".correction-controls",
            "@media (max-width: 390px)",
        ):
            self.assertIn(contract, css)
        self.assertIn(".diagnostic-technical a:not(.btn)", css)


    def test_apply_rolls_back_and_hides_sql_error(self):
        token = self.preview_token(self.preview())
        with db.get_connection() as conn:
            conn.execute(
                """
                CREATE TRIGGER reject_manual_correction
                BEFORE UPDATE ON items
                WHEN NEW.price_parse_source = 'manual_correction'
                BEGIN
                    SELECT RAISE(ABORT, 'secret sql detail');
                END
                """
            )
            conn.commit()

        response = self.client.post(
            f"/data-quality/prices/{self.item_id}/correct",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Не удалось применить исправление", html)
        self.assertNotIn("secret sql detail", html)
        after = self.item_row(self.item_id)
        self.assertIsNone(after["package_size"])
        self.assertEqual(after["price_parse_source"], "inferred_piece")

    def test_apply_rejects_item_deleted_after_preview(self):
        token = self.preview_token(self.preview())
        with db.get_connection() as conn:
            conn.execute("DELETE FROM items WHERE id = ?", (self.item_id,))
            conn.commit()

        response = self.client.post(
            f"/data-quality/prices/{self.item_id}/correct",
            data={
                "action": "apply",
                "preview_token": token,
                "quantity_unit": "piece",
                "package_size": "400",
                "package_unit": "g",
            },
        )

        self.assertEqual(response.status_code, 404)
        with db.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)

if __name__ == "__main__":
    unittest.main()
