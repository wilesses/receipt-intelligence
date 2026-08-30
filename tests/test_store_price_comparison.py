import unittest

try:
    from app.store_price_comparison import build_store_price_comparison
except ImportError:
    build_store_price_comparison = None


class StorePriceComparisonTests(unittest.TestCase):
    def observation(
        self,
        store,
        normalized_price,
        *,
        date="2026-06-01",
        name="Test product 500g",
        effective_name="Test product",
        canonical_name="Test product",
        normalized_unit="eur_per_kg",
        quantity=1,
        line_total=5,
        unit_price=5,
        quantity_unit="piece",
        package_size=500,
        package_unit="g",
        source="package_name",
        confidence=0.85,
    ):
        return {
            "effective_name": effective_name,
            "name": name,
            "canonical_name": canonical_name,
            "normalized_name": name.lower(),
            "store": store,
            "date": date,
            "quantity": quantity,
            "price": line_total,
            "line_total": line_total,
            "unit_price": unit_price,
            "quantity_unit": quantity_unit,
            "package_size": package_size,
            "package_unit": package_unit,
            "normalized_unit_price": normalized_price,
            "normalized_price_unit": normalized_unit,
            "price_parse_source": source,
            "price_parse_confidence": confidence,
        }

    def build(self, observations):
        self.assertIsNotNone(
            build_store_price_comparison,
            "store comparison service has not been implemented",
        )
        return build_store_price_comparison(observations)

    def test_comparable_uses_store_medians_and_percentage_difference(self):
        observations = [
            self.observation("MAXIMA", value, date=f"2026-06-0{index}")
            for index, value in enumerate((10, 12, 14), start=1)
        ] + [
            self.observation("RIMI", value, date=f"2026-07-0{index}")
            for index, value in enumerate((12, 15, 18), start=1)
        ]

        result = self.build(observations)

        self.assertEqual(result["evidence_level"], "COMPARABLE")
        self.assertEqual([store["store"] for store in result["stores"]], ["MAXIMA", "RIMI"])
        self.assertEqual(result["stores"][0]["median_price"], 12)
        self.assertEqual(result["stores"][1]["median_price"], 15)
        self.assertEqual(result["stores"][0]["min_price"], 10)
        self.assertEqual(result["stores"][0]["max_price"], 14)
        self.assertEqual(result["stores"][1]["latest_date"], "2026-07-03")
        self.assertEqual(result["cheapest_store"], "MAXIMA")
        self.assertEqual(result["comparison_store"], "RIMI")
        self.assertEqual(result["difference_percent"], 20.0)

    def test_preliminary_keeps_prices_but_withholds_winner_and_difference(self):
        result = self.build([
            self.observation("MAXIMA", 10),
            self.observation("RIMI", 12),
        ])

        self.assertEqual(result["evidence_level"], "PRELIMINARY")
        self.assertEqual([store["observation_count"] for store in result["stores"]], [1, 1])
        self.assertIsNone(result["cheapest_store"])
        self.assertIsNone(result["difference_percent"])

    def test_limited_shows_only_qualified_observed_difference(self):
        result = self.build([
            self.observation("MAXIMA", 10),
            self.observation("MAXIMA", 14),
            self.observation("RIMI", 12),
            self.observation("RIMI", 16),
        ])

        self.assertEqual(result["evidence_level"], "LIMITED")
        self.assertEqual(result["cheapest_store"], "MAXIMA")
        self.assertEqual(result["difference_percent"], 14.3)
        self.assertFalse(result["strong_claim_allowed"])

    def test_one_store_returns_honest_ineligible_reason(self):
        result = self.build([
            self.observation("MAXIMA", 10),
            self.observation("MAXIMA", 12),
            self.observation("MAXIMA", 14),
        ])

        self.assertEqual(result["reason"], "only_one_store")
        self.assertEqual(result["stores"], [])
        self.assertIsNone(result["evidence_level"])

    def test_mixed_denominators_are_never_compared(self):
        result = self.build([
            self.observation("MAXIMA", 10, normalized_unit="eur_per_kg"),
            self.observation("RIMI", 2, normalized_unit="eur_per_piece"),
        ])

        self.assertEqual(result["reason"], "incompatible_price_units")
        self.assertEqual(result["stores"], [])

    def test_bad_price_evidence_does_not_enter_median(self):
        observations = [
            self.observation("MAXIMA", value) for value in (10, 12, 14)
        ] + [
            self.observation("RIMI", value) for value in (15, 16, 17)
        ]
        observations.extend([
            self.observation("MAXIMA", 100, confidence=None),
            self.observation("MAXIMA", 100, quantity=2, line_total=5, unit_price=3),
            self.observation("MAXIMA", 100, name="Test product 2x500g"),
            self.observation("RIMI", 100, name="Depozīta maksa", package_size=None, package_unit=None),
            self.observation("RIMI", None),
        ])

        result = self.build(observations)

        self.assertEqual(result["evidence_level"], "COMPARABLE")
        self.assertEqual([store["observation_count"] for store in result["stores"]], [3, 3])
        self.assertEqual([store["median_price"] for store in result["stores"]], [12, 16])

    def test_more_than_two_stores_rank_deterministically_against_runner_up(self):
        observations = []
        for store, values in (
            ("RIMI", (11, 12, 13)),
            ("LIDL", (9, 10, 11)),
            ("MAXIMA", (13, 14, 15)),
        ):
            observations.extend(self.observation(store, value) for value in values)

        result = self.build(observations)

        self.assertEqual([store["store"] for store in result["stores"]], ["LIDL", "RIMI", "MAXIMA"])
        self.assertEqual(result["cheapest_store"], "LIDL")
        self.assertEqual(result["comparison_store"], "RIMI")
        self.assertEqual(result["difference_percent"], 16.7)

    def test_equal_medians_do_not_invent_a_winner(self):
        result = self.build([
            *[self.observation("MAXIMA", value) for value in (10, 12, 14)],
            *[self.observation("RIMI", value) for value in (11, 12, 13)],
        ])

        self.assertEqual(result["evidence_level"], "COMPARABLE")
        self.assertTrue(result["is_tie"])
        self.assertIsNone(result["cheapest_store"])
        self.assertIsNone(result["difference_percent"])

    def test_legacy_rows_without_price_model_fields_fail_closed(self):
        result = self.build([
            self.observation("MAXIMA", None, line_total=None, unit_price=None, source=None, confidence=None),
            self.observation("RIMI", None, line_total=None, unit_price=None, source=None, confidence=None),
        ])

        self.assertEqual(result["reason"], "insufficient_comparable_prices")

    def test_null_canonical_name_uses_exact_persisted_raw_identity(self):
        result = self.build([
            self.observation("MAXIMA", 10, effective_name="Exact raw product", canonical_name=None),
            self.observation("RIMI", 12, effective_name="Exact raw product", canonical_name=None),
        ])

        self.assertEqual(result["evidence_level"], "PRELIMINARY")

    def test_mixed_canonical_provenance_fails_closed_as_unresolved_identity(self):
        result = self.build([
            self.observation("MAXIMA", 10, effective_name="Mixed identity", canonical_name="Mixed identity"),
            self.observation("RIMI", 12, effective_name="Mixed identity", canonical_name=None),
        ])

        self.assertEqual(result["reason"], "unresolved_product_identity")

    def test_audited_unresolved_identity_cannot_produce_store_comparison(self):
        observations = []
        for store in ("MAXIMA", "RIMI"):
            observations.extend(
                self.observation(
                    store,
                    value,
                    name="Dilles 30g",
                    effective_name="dilles 30g",
                    canonical_name="dilles 30g",
                )
                for value in (20, 25, 30)
            )

        result = self.build(observations)

        self.assertEqual(result["reason"], "unresolved_product_identity")
        self.assertIsNone(result["evidence_level"])

    def test_even_median_and_latest_date_are_deterministic(self):
        observations = []
        for store, values in (("MAXIMA", (10, 12, 14, 16)), ("RIMI", (20, 22, 24, 26))):
            observations.extend(
                self.observation(store, value, date=f"2026-06-0{index}")
                for index, value in enumerate(values, start=1)
            )

        result = self.build(observations)

        self.assertEqual(result["stores"][0]["median_price"], 13)
        self.assertEqual(result["stores"][0]["latest_date"], "2026-06-04")


if __name__ == "__main__":
    unittest.main()
