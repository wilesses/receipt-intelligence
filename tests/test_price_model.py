import unittest

from app.price_model import (
    are_price_units_comparable,
    derive_price_data,
    extract_package_size,
)
from app.product_normalizer import normalize_product_name


class PriceModelTest(unittest.TestCase):
    def assert_unresolved(self, data):
        self.assertIsNone(data.package_size)
        self.assertIn(data.package_unit, (None, "unknown"))
        self.assertIsNone(data.normalized_unit_price)
        self.assertEqual(data.normalized_price_unit, "unknown")
        self.assertIsNone(data.confidence)

    def test_explicit_parser_kg_keeps_trusted_weighted_evidence(self):
        data = derive_price_data(
            name="Siers",
            quantity=0.742,
            unit_price=7.99,
            line_total=5.93,
            quantity_unit="kg",
            source="parser",
        )

        self.assertEqual(data.quantity, 0.742)
        self.assertEqual(data.unit_price, 7.99)
        self.assertLessEqual(
            abs(data.quantity * data.unit_price - data.line_total),
            max(0.02, data.line_total * 0.02),
        )
        self.assertEqual(data.source, "parser")
        self.assertEqual(data.confidence, 0.95)
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertAlmostEqual(data.normalized_unit_price, 5.93 / 0.742, places=4)

    def test_explicit_parser_piece_with_clean_package_keeps_priority(self):
        data = derive_price_data(
            name="Siers 750g",
            quantity=2,
            unit_price=4.5,
            line_total=9,
            quantity_unit="gab",
            source="parser",
        )

        self.assertEqual(data.quantity_unit, "piece")
        self.assertEqual(data.package_size, 750)
        self.assertEqual(data.package_unit, "g")
        self.assertEqual(data.source, "parser")
        self.assertEqual(data.confidence, 0.95)
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertEqual(data.normalized_unit_price, 6)

    def test_fractional_unknown_unit_infers_terminal_kg_when_prices_agree(self):
        data = derive_price_data(
            name="Siers kg",
            quantity=0.742,
            unit_price=7.99,
            line_total=5.93,
        )

        self.assertEqual(data.quantity_unit, "kg")
        self.assertEqual(data.confidence, 0.75)
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertAlmostEqual(data.normalized_unit_price, 5.93 / 0.742, places=4)

    def test_fractional_unknown_unit_with_inconsistent_price_stays_unresolved(self):
        data = derive_price_data(
            name="Siers kg",
            quantity=0.742,
            unit_price=5,
            line_total=5.93,
        )

        self.assert_unresolved(data)
        self.assertIn("line_total_unit_price_mismatch", data.warnings)

    def test_fractional_unknown_unit_without_unit_price_stays_unresolved(self):
        data = derive_price_data(
            name="Siers kg",
            quantity=0.742,
            line_total=5.93,
        )

        self.assert_unresolved(data)

    def test_clean_package_infers_piece_semantics(self):
        data = derive_price_data(
            name="Siers 750g",
            quantity=1,
            unit_price=4.5,
            line_total=4.5,
        )

        self.assertEqual(data.quantity_unit, "piece")
        self.assertEqual(data.package_size, 750)
        self.assertEqual(data.package_unit, "g")
        self.assertEqual(data.confidence, 0.85)
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertEqual(data.normalized_unit_price, 6)

    def test_multiple_identical_packages_use_total_package_mass(self):
        data = derive_price_data(
            name="Siers 750g",
            quantity=3,
            unit_price=4.5,
            line_total=13.5,
        )

        self.assertEqual(data.package_size, 750)
        self.assertEqual(data.quantity_unit, "piece")
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertEqual(data.normalized_unit_price, 6)

    def test_piece_package_count_normalizes_price_per_piece(self):
        cases = (
            ("Olas 30gab", 1, 2.99, 0.0997),
            ("Olas 10gab", 2, 4, 0.2),
            ("Tabletes 60gab", 1, 12, 0.2),
            ("Kapsulas 60gab", 1, 12, 0.2),
        )

        for name, quantity, total, expected_price in cases:
            with self.subTest(name=name):
                data = derive_price_data(name=name, quantity=quantity, line_total=total)

                self.assertEqual(data.quantity_unit, "piece")
                self.assertEqual(data.package_size, int(name.split()[-1][:-3]))
                self.assertEqual(data.package_unit, "piece")
                self.assertEqual(data.normalized_price_unit, "eur_per_piece")
                self.assertEqual(data.normalized_unit_price, expected_price)
                self.assertEqual(data.source, "package_name")
                self.assertEqual(data.confidence, 0.85)

    def test_piece_inference_without_package_count_stays_inferred_piece(self):
        data = derive_price_data(name="Olas", quantity=2, line_total=4)

        self.assertEqual(data.quantity_unit, "piece")
        self.assertEqual(data.normalized_price_unit, "eur_per_piece")
        self.assertEqual(data.normalized_unit_price, 2)
        self.assertEqual(data.source, "inferred_piece")
        self.assertEqual(data.confidence, 0.70)

    def test_ambiguous_or_invalid_piece_package_counts_stay_unresolved(self):
        for name in ("Burgeru maizītes 6gab. 300g", "Olas 2x10gab", "Olas 0gab", "Olas 2,5gab"):
            with self.subTest(name=name):
                data = derive_price_data(name=name, quantity=1, line_total=4)

                self.assert_unresolved(data)
                self.assertTrue(
                    {"ambiguous_package_size", "invalid_package_size", "multipack_unresolved"}
                    .intersection(data.warnings)
                )

    def test_piece_counts_in_sets_stay_unresolved(self):
        for name in (
            "Masāžas bumbiņu komplekts 2gab.",
            "Mānekļi PHILIPS AVENT silik. 0-6m. 2gab.",
            "Mānekļ. PHILIPS AVENT Ultr. Air 6-18m. 2gb.",
            "Zīdaiņu vannas rotaļlietas FOXTER 8gab.",
        ):
            with self.subTest(name=name):
                data = derive_price_data(name=name, quantity=1, line_total=4)

                self.assert_unresolved(data)
                self.assertIn("ambiguous_package_size", data.warnings)

    def test_kit_brand_is_not_mistaken_for_a_set(self):
        data = derive_price_data(name="KIT KAT 2gab", quantity=1, line_total=1.20)

        self.assertEqual(data.source, "package_name")
        self.assertEqual(data.normalized_unit_price, 0.60)
        self.assertEqual(data.normalized_price_unit, "eur_per_piece")

    def test_decimal_comma_liter_package_parses_to_ml(self):
        package = extract_package_size(
            "Piens 1,5L",
            normalize_product_name("Piens 1,5L"),
        )

        self.assertEqual(package, (1500, "ml", []))

    def test_malformed_decimal_package_is_rejected(self):
        data = derive_price_data(
            name="Piens 1, 5L",
            quantity=1,
            unit_price=2.4,
            line_total=2.4,
            quantity_unit="gab",
            source="parser",
        )

        self.assert_unresolved(data)
        self.assertIn("ambiguous_package_size", data.warnings)

    def test_large_weight_is_not_treated_as_a_package(self):
        data = derive_price_data(
            name="Miltu maiss 45kg",
            quantity=1,
            unit_price=20,
            line_total=20,
            quantity_unit="gab",
            source="parser",
        )

        self.assert_unresolved(data)
        self.assertIn("ambiguous_package_size", data.warnings)

    def test_explicit_parser_weight_survives_large_package_warning(self):
        data = derive_price_data(
            name="Miltu maiss 45kg",
            quantity=0.5,
            unit_price=20,
            line_total=10,
            quantity_unit="kg",
            source="parser",
        )

        self.assertIsNone(data.package_size)
        self.assertIn("ambiguous_package_size", data.warnings)
        self.assertEqual(data.source, "parser")
        self.assertEqual(data.confidence, 0.95)
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertEqual(data.normalized_unit_price, 20)

    def test_parser_supplied_package_outranks_ambiguous_name(self):
        data = derive_price_data(
            name="Siers 45kg",
            quantity=2,
            unit_price=4.5,
            line_total=9,
            quantity_unit="gab",
            package_size=750,
            package_unit="g",
            source="parser",
        )

        self.assertEqual(data.package_size, 750)
        self.assertEqual(data.package_unit, "g")
        self.assertEqual(data.normalized_unit_price, 6)
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertEqual(data.confidence, 0.95)

    def test_glued_package_token_is_rejected(self):
        data = derive_price_data(
            name="sviestu250g",
            quantity=1,
            unit_price=3,
            line_total=3,
            quantity_unit="gab",
            source="parser",
        )

        self.assert_unresolved(data)
        self.assertIn("ambiguous_package_size", data.warnings)

    def test_receipt_prefix_is_parser_contamination(self):
        data = derive_price_data(
            name="Piens Čeks 218/751 1L",
            quantity=1,
            unit_price=2,
            line_total=2,
            quantity_unit="gab",
            source="parser",
        )

        self.assert_unresolved(data)
        self.assertIn("parser_contamination", data.warnings)

    def test_multipacks_stay_unresolved(self):
        for name in ("Konfektes 11x12,6g", "Alus 6 x 330 ml"):
            with self.subTest(name=name):
                data = derive_price_data(
                    name=name,
                    quantity=1,
                    unit_price=6,
                    line_total=6,
                    quantity_unit="gab",
                    source="parser",
                )

                self.assert_unresolved(data)
                self.assertIn("multipack_unresolved", data.warnings)

    def test_safe_inferred_piece_requires_explicit_line_total(self):
        data = derive_price_data(name="Maize", quantity=2, line_total=3)

        self.assertEqual(data.quantity_unit, "piece")
        self.assertEqual(data.confidence, 0.70)
        self.assertEqual(data.normalized_price_unit, "eur_per_piece")
        self.assertEqual(data.normalized_unit_price, 1.5)

    def test_missing_price_evidence_does_not_create_per_piece_price(self):
        data = derive_price_data(name="Maize", quantity=2)

        self.assertIsNone(data.unit_price)
        self.assertIsNone(data.normalized_unit_price)
        self.assertEqual(data.normalized_price_unit, "unknown")
        self.assertIsNone(data.confidence)

    def test_service_like_fee_and_bag_lines_do_not_create_normalized_prices(self):
        for name in (
            "Papildus depozīta maksa",
            "Deposit fee",
            "Papīra iepirkumu maisiņš PALDIES",
            "Paper bag",
            "Atkārtoti lietojams maisiņš",
            "Reusable bag",
            "Iepakojums",
            "Packaging",
        ):
            with self.subTest(name=name):
                data = derive_price_data(name=name, quantity=1, line_total=0.19)

                self.assertIsNone(data.normalized_unit_price)
                self.assertEqual(data.normalized_price_unit, "unknown")
                self.assertIsNone(data.confidence)
                self.assertEqual(data.source, "service_line")
                self.assertIn("service_line", data.warnings)

    def test_service_like_word_in_normal_product_name_does_not_reject_product(self):
        data = derive_price_data(
            name="Papīra dvieļi BLOOM Comfort 500g",
            quantity=1,
            line_total=2.69,
        )

        self.assertEqual(data.quantity_unit, "piece")
        self.assertEqual(data.package_size, 500)
        self.assertEqual(data.package_unit, "g")
        self.assertEqual(data.normalized_price_unit, "eur_per_kg")
        self.assertEqual(data.normalized_unit_price, 5.38)
        self.assertEqual(data.confidence, 0.85)

    def test_fatal_warning_clears_outputs_for_explicit_piece(self):
        data = derive_price_data(
            name="Čeks sviestu250g",
            quantity=1,
            unit_price=3,
            line_total=3,
            quantity_unit="gab",
            source="parser",
        )

        self.assertEqual(data.quantity_unit, "piece")
        self.assert_unresolved(data)
        self.assertIn("parser_contamination", data.warnings)

    def test_normalized_weight_and_volume_units_are_comparable_by_unit(self):
        self.assertTrue(are_price_units_comparable(
            {"normalized_price_unit": "eur_per_kg"},
            {"normalized_price_unit": "eur_per_kg"},
        ))
        self.assertFalse(are_price_units_comparable(
            {"normalized_price_unit": "eur_per_l"},
            {"normalized_price_unit": "eur_per_kg"},
        ))

    def test_zero_quantity_does_not_divide_by_zero(self):
        data = derive_price_data(
            name="Siers 750g",
            quantity=0,
            unit_price=4.5,
            line_total=4.5,
            quantity_unit="gab",
            source="parser",
        )

        self.assertIsNone(data.normalized_unit_price)
        self.assertEqual(data.normalized_price_unit, "unknown")
        self.assertIn("quantity_not_positive", data.warnings)


if __name__ == "__main__":
    unittest.main()
