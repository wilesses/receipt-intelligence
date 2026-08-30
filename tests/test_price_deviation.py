import unittest

from app.price_deviation import (
    evaluate_price_deviation,
    price_observation_ineligibility_reason,
)


class PriceDeviationTests(unittest.TestCase):
    def observation(
        self,
        item_id,
        price,
        *,
        receipt_id=None,
        receipt_date=None,
        unit="eur_per_l",
        **overrides,
    ):
        row = {
            "id": item_id,
            "receipt_id": receipt_id or item_id,
            "effective_name": "Milk 1L",
            "name": "Milk 1L",
            "canonical_name": "Milk 1L",
            "normalized_name": "milk 1l",
            "store": "RIMI",
            "date": receipt_date or f"2026-01-{item_id:02d}",
            "quantity": 1,
            "price": price,
            "line_total": price,
            "unit_price": price,
            "quantity_unit": "piece",
            "package_size": 1000,
            "package_unit": "ml",
            "normalized_unit_price": price,
            "normalized_price_unit": unit,
            "price_parse_source": "package_name",
            "price_parse_confidence": 0.85,
        }
        row.update(overrides)
        return row

    def test_current_observation_never_enters_its_own_median(self):
        history = [self.observation(index, 2) for index in (1, 2, 3)]
        current = self.observation(4, 4)

        result = evaluate_price_deviation(current, [*history, current])

        self.assertEqual(result["eligible_prior_observation_count"], 3)
        self.assertEqual(result["historical_median"], 2)
        self.assertEqual(result["status"], "MORE_EXPENSIVE_THAN_USUAL")

    def test_only_observations_before_current_are_used(self):
        history = [self.observation(index, 2) for index in (1, 2, 3)]
        current = self.observation(4, 3)
        future = self.observation(5, 100)

        result = evaluate_price_deviation(current, [*history, current, future])

        self.assertEqual(result["historical_median"], 2)
        self.assertEqual(result["eligible_prior_observation_count"], 3)

    def test_legacy_price_divided_by_quantity_cannot_create_status(self):
        history = [
            self.observation(
                index,
                2,
                normalized_unit_price=None,
                normalized_price_unit="unknown",
            )
            for index in (1, 2, 3)
        ]
        current = self.observation(
            4,
            4,
            normalized_unit_price=None,
            normalized_price_unit="unknown",
        )

        result = evaluate_price_deviation(current, [*history, current])

        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result["reason"], "missing_normalized_price")

    def test_incompatible_normalized_units_never_mix(self):
        history = [self.observation(index, 2, unit="eur_per_kg") for index in (1, 2, 3)]
        current = self.observation(4, 4, unit="eur_per_piece")

        result = evaluate_price_deviation(current, [*history, current])

        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result["eligible_prior_observation_count"], 0)

    def test_bad_price_evidence_is_rejected_with_deterministic_reason(self):
        cases = {
            "low_confidence": {"price_parse_confidence": 0.70},
            "unsupported_source": {"price_parse_source": "inferred_piece"},
            "arithmetic_mismatch": {"unit_price": 1},
            "service_line": {"name": "Depozīta maksa", "effective_name": "Depozīta maksa", "canonical_name": "Depozīta maksa"},
            "parser_contamination": {"name": "Receipt Milk 1L"},
            "unresolved_multipack": {"name": "Milk 2x1L"},
            "ambiguous_measurement": {"name": "Milk 1, 5L", "package_size": None, "package_unit": None},
        }

        for expected, overrides in cases.items():
            with self.subTest(reason=expected):
                self.assertEqual(
                    price_observation_ineligibility_reason(self.observation(1, 2, **overrides)),
                    expected,
                )

    def test_fewer_than_three_prior_observations_fails_closed(self):
        current = self.observation(3, 4)

        result = evaluate_price_deviation(current, [self.observation(1, 2), self.observation(2, 2), current])

        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result["reason"], "insufficient_prior_history")

    def test_normal_price_uses_prior_median(self):
        history = [self.observation(index, 2) for index in (1, 2, 3)]
        current = self.observation(4, 2.1)

        result = evaluate_price_deviation(current, [*history, current])

        self.assertEqual(result["status"], "NORMAL")
        self.assertAlmostEqual(result["deviation_percent"], 5)

    def test_positive_fifteen_percent_is_more_expensive(self):
        history = [self.observation(index, 2) for index in (1, 2, 3)]
        current = self.observation(4, 2.3)

        result = evaluate_price_deviation(current, [*history, current])

        self.assertEqual(result["status"], "MORE_EXPENSIVE_THAN_USUAL")

    def test_negative_ten_percent_is_cheaper(self):
        history = [self.observation(index, 2) for index in (1, 2, 3)]
        current = self.observation(4, 1.8)

        result = evaluate_price_deviation(current, [*history, current])

        self.assertEqual(result["status"], "CHEAPER_THAN_USUAL")

    def test_same_day_order_uses_receipt_then_item_id(self):
        same_day = "2026-01-10"
        prior = [
            self.observation(1, 2, receipt_id=10, receipt_date=same_day),
            self.observation(2, 2, receipt_id=10, receipt_date=same_day),
            self.observation(3, 2, receipt_id=11, receipt_date=same_day),
        ]
        current = self.observation(4, 4, receipt_id=11, receipt_date=same_day)
        later = self.observation(5, 100, receipt_id=12, receipt_date=same_day)

        result = evaluate_price_deviation(current, [later, current, *reversed(prior)])

        self.assertEqual(result["eligible_prior_observation_count"], 3)
        self.assertEqual(result["historical_median"], 2)
        self.assertEqual(result["status"], "MORE_EXPENSIVE_THAN_USUAL")

    def test_history_older_than_180_days_is_excluded(self):
        current = self.observation(4, 4, receipt_date="2026-08-01")
        observations = [
            self.observation(1, 2, receipt_date="2026-01-01"),
            self.observation(2, 2, receipt_date="2026-06-01"),
            self.observation(3, 2, receipt_date="2026-07-01"),
            current,
        ]

        result = evaluate_price_deviation(current, observations)

        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result["eligible_prior_observation_count"], 2)


if __name__ == "__main__":
    unittest.main()
