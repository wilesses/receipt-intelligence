import unittest

from app.analytics_service import build_normalized_price_trend


class NormalizedPriceTrendTests(unittest.TestCase):
    def observation(self, price, *, month="2026-06", unit="eur_per_kg", **overrides):
        row = {
            "id": 1,
            "receipt_id": 1,
            "effective_name": "Safe product",
            "name": "Safe product 500g",
            "canonical_name": "Safe product",
            "normalized_name": "safe product 500g",
            "store": "RIMI",
            "date": f"{month}-10",
            "quantity": 1,
            "price": 2.5,
            "line_total": 2.5,
            "unit_price": 2.5,
            "quantity_unit": "piece",
            "package_size": 500,
            "package_unit": "g",
            "normalized_unit_price": price,
            "normalized_price_unit": unit,
            "price_parse_source": "package_name",
            "price_parse_confidence": 0.95,
        }
        row.update(overrides)
        return row

    def test_supported_units_are_returned_with_explicit_denominator(self):
        cases = {
            "eur_per_kg": "€/kg",
            "eur_per_l": "€/L",
            "eur_per_piece": "€/шт.",
        }

        for unit, label in cases.items():
            with self.subTest(unit=unit):
                observation = self.observation(3.5, unit=unit)
                if unit == "eur_per_l":
                    observation.update(package_size=1000, package_unit="ml", name="Safe product 1L")
                elif unit == "eur_per_piece":
                    observation.update(package_size=1, package_unit="piece", name="Safe product")

                result = build_normalized_price_trend([observation])

                self.assertEqual(result["status"], "ready")
                self.assertEqual(result["normalized_price_unit"], unit)
                self.assertEqual(result["unit_label"], label)
                self.assertEqual(result["values"], [3.5])

    def test_monthly_value_is_median_and_reports_observation_count(self):
        rows = [
            self.observation(2, id=1, receipt_id=1),
            self.observation(100, id=2, receipt_id=2),
            self.observation(4, id=3, receipt_id=3),
            self.observation(8, id=4, receipt_id=4, month="2026-07"),
        ]

        result = build_normalized_price_trend(rows)

        self.assertEqual(result["labels"], ["2026-06", "2026-07"])
        self.assertEqual(result["values"], [4.0, 8.0])
        self.assertEqual(result["observation_counts"], [3, 1])

    def test_incompatible_units_fail_closed(self):
        result = build_normalized_price_trend([
            self.observation(4, unit="eur_per_kg"),
            self.observation(
                2,
                unit="eur_per_piece",
                id=2,
                receipt_id=2,
                package_size=1,
                package_unit="piece",
                name="Safe product",
            ),
        ])

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "incompatible_price_units")
        self.assertEqual(result["values"], [])

    def test_unsafe_and_legacy_observations_never_become_trend_points(self):
        rows = [
            self.observation(None, id=1, normalized_price_unit="unknown"),
            self.observation(50, id=2, receipt_id=2, price_parse_confidence=0.5),
            self.observation(50, id=3, receipt_id=3, quantity=2, unit_price=2),
            self.observation(50, id=4, receipt_id=4, name="Safe product 2x500g"),
        ]

        result = build_normalized_price_trend(rows)

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "no_comparable_history")
        self.assertEqual(result["labels"], [])


if __name__ == "__main__":
    unittest.main()
