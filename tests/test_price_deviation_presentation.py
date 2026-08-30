import unittest

from app.web.routes import build_price_evaluation


class PriceDeviationPresentationTests(unittest.TestCase):
    def observation(self, item_id, price, **overrides):
        row = {
            "id": item_id,
            "receipt_id": item_id,
            "effective_name": "Milk 1L",
            "name": "Milk 1L",
            "canonical_name": "Milk 1L",
            "normalized_name": "milk 1l",
            "store": "RIMI",
            "date": f"2026-01-{item_id:02d}",
            "quantity": 1,
            "price": price,
            "line_total": price,
            "unit_price": price,
            "quantity_unit": "piece",
            "package_size": 1000,
            "package_unit": "ml",
            "normalized_unit_price": price,
            "normalized_price_unit": "eur_per_l",
            "price_parse_source": "package_name",
            "price_parse_confidence": 0.95,
        }
        row.update(overrides)
        return row

    def test_zero_one_and_two_prior_observations_show_exact_progress(self):
        for prior_count in (0, 1, 2):
            with self.subTest(prior_count=prior_count):
                history = [self.observation(index, 2) for index in range(1, prior_count + 1)]
                current = self.observation(prior_count + 1, 2)

                result = build_price_evaluation(current, [*history, current])
                evidence = result["evidence"]

                self.assertFalse(result["has_enough_data"])
                self.assertEqual(evidence["category"], "NOT_ENOUGH_HISTORY")
                self.assertEqual(evidence["eligible_prior_count"], prior_count)
                self.assertEqual(evidence["required_prior_count"], 3)
                self.assertEqual(evidence["remaining_count"], 3 - prior_count)
                self.assertTrue(evidence["show_progress"])
                self.assertEqual(
                    evidence["progress_text"],
                    f"Сопоставимых наблюдений: {prior_count} из 3.",
                )

    def test_current_price_blocker_hides_history_progress(self):
        current = self.observation(
            3,
            2,
            normalized_unit_price=None,
            normalized_price_unit="unknown",
        )

        result = build_price_evaluation(
            current,
            [self.observation(1, 2), self.observation(2, 2), current],
        )
        evidence = result["evidence"]

        self.assertEqual(evidence["category"], "PRICE_NOT_COMPARABLE")
        self.assertEqual(evidence["title"], "Цена пока несопоставима")
        self.assertFalse(evidence["show_progress"])
        self.assertIsNone(evidence["eligible_prior_count"])
        self.assertIsNone(evidence["progress_text"])

    def test_identity_blocker_has_distinct_explanation(self):
        current = self.observation(
            1,
            2,
            effective_name="Dilles 100g",
            name="Dilles 100g",
            canonical_name="Dilles 100g",
        )

        evidence = build_price_evaluation(current, [current])["evidence"]

        self.assertEqual(evidence["category"], "PRODUCT_IDENTITY_UNCERTAIN")
        self.assertEqual(evidence["title"], "История товара требует уточнения")
        self.assertFalse(evidence["show_progress"])

    def test_quality_reasons_map_to_review_state(self):
        cases = {
            "arithmetic": {"unit_price": 1},
            "ambiguous_measurement": {
                "name": "Milk 1, 5L",
                "package_size": None,
                "package_unit": None,
            },
            "parser_contamination": {"name": "Receipt Milk 1L"},
        }

        for case, overrides in cases.items():
            with self.subTest(case=case):
                current = self.observation(1, 2, **overrides)
                evidence = build_price_evaluation(current, [current])["evidence"]

                self.assertEqual(evidence["category"], "EVIDENCE_NEEDS_REVIEW")
                self.assertEqual(evidence["title"], "Данные требуют проверки")
                self.assertFalse(evidence["show_progress"])

    def test_identity_precedes_current_price_and_history_blockers(self):
        current = self.observation(
            1,
            2,
            effective_name="Dilles 100g",
            name="Dilles 100g",
            canonical_name="Dilles 100g",
            normalized_unit_price=None,
            normalized_price_unit="unknown",
        )

        result = build_price_evaluation(current, [current])

        self.assertEqual(result["reason"], "unresolved_product_identity")
        self.assertEqual(result["evidence"]["category"], "PRODUCT_IDENTITY_UNCERTAIN")

    def test_success_labels_and_percentages_are_unchanged(self):
        history = [self.observation(index, 2) for index in (1, 2, 3)]
        cases = (
            (1.8, "🔥 Выгодная цена", -10.0),
            (2.1, "Обычная цена", 5.0),
            (2.3, "⚠️ Дороже обычного", 15.0),
        )

        for price, label, percent in cases:
            with self.subTest(price=price):
                current = self.observation(4, price)
                result = build_price_evaluation(current, [*history, current])

                self.assertTrue(result["has_enough_data"])
                self.assertEqual(result["status"], label)
                self.assertEqual(result["median_deviation"], percent)
                self.assertNotIn("evidence", result)


if __name__ == "__main__":
    unittest.main()
