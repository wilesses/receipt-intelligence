import unittest

from app.price_correction import (
    CorrectionError,
    build_correction_preview,
    classify_price_correction,
)


def price_row(**overrides):
    row = {
        "id": 7,
        "receipt_id": 3,
        "name": "Jogurts 400g",
        "normalized_name": "jogurts 400g",
        "canonical_name": None,
        "category": "молочные продукты и альтернативы",
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
        "store": "TEST",
        "date": "2026-08-23",
    }
    row.update(overrides)
    return row


class PriceCorrectionPreviewTests(unittest.TestCase):
    def test_missing_package_preview_uses_authoritative_normalized_price(self):
        preview = build_correction_preview(
            price_row(),
            {"quantity_unit": "piece", "package_size": "400", "package_unit": "g"},
        )

        self.assertEqual(preview["after"]["normalized_unit_price"], 5.0)
        self.assertEqual(preview["after"]["normalized_price_unit"], "eur_per_kg")
        self.assertEqual(preview["after"]["price_parse_source"], "manual_correction")
        self.assertEqual(preview["after"]["price_parse_confidence"], 0.85)
        self.assertFalse(preview["eligible_before"])
        self.assertTrue(preview["eligible_after"])

    def test_quantity_unit_preview_uses_paid_total_denominator(self):
        preview = build_correction_preview(
            price_row(
                name="Tomāti kg",
                normalized_name="tomāti kg",
                quantity=0.5,
                price=1.5,
                line_total=1.5,
                unit_price=3.0,
                quantity_unit="unknown",
                normalized_unit_price=None,
                normalized_price_unit="unknown",
                price_parse_source="unresolved",
                price_parse_confidence=None,
            ),
            {"quantity_unit": "kg", "package_size": "", "package_unit": "unknown"},
        )

        self.assertEqual(preview["after"]["normalized_unit_price"], 3.0)
        self.assertEqual(preview["after"]["normalized_price_unit"], "eur_per_kg")

    def test_zero_or_negative_package_size_is_rejected(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(CorrectionError, "размер упаковки"):
                    build_correction_preview(
                        price_row(),
                        {"quantity_unit": "piece", "package_size": value, "package_unit": "g"},
                    )

    def test_physical_quantity_unit_rejects_package_denominator(self):
        with self.assertRaisesRegex(CorrectionError, "упаковк"):
            build_correction_preview(
                price_row(quantity_unit="unknown"),
                {"quantity_unit": "kg", "package_size": "400", "package_unit": "g"},
            )

    def test_manual_correction_does_not_bypass_multipack_guard(self):
        row = price_row(name="Йогурт 6x110g", normalized_name="йогурт 6x110g")

        self.assertEqual(classify_price_correction(row)["classification"], "NOT_CORRECTABLE_V1")
        with self.assertRaisesRegex(CorrectionError, "multipack"):
            build_correction_preview(
                row,
                {"quantity_unit": "piece", "package_size": "110", "package_unit": "g"},
            )

    def test_manual_correction_resolves_ambiguous_measurement_only_with_structured_package(self):
        row = price_row(
            name="Напиток 1, 51 L",
            normalized_name="напиток 1 51 l",
            quantity_unit="unknown",
            normalized_unit_price=None,
            normalized_price_unit="unknown",
            price_parse_source="rejected",
            price_parse_confidence=None,
        )

        with self.assertRaisesRegex(CorrectionError, "Неоднознач"):
            build_correction_preview(
                row,
                {"quantity_unit": "piece", "package_size": "", "package_unit": "unknown"},
            )

        preview = build_correction_preview(
            row,
            {"quantity_unit": "piece", "package_size": "1500", "package_unit": "ml"},
        )
        self.assertEqual(preview["after"]["normalized_price_unit"], "eur_per_l")

    def test_manual_correction_does_not_bypass_arithmetic_guard(self):
        row = price_row(quantity=2, line_total=3.10, unit_price=1.99)

        self.assertEqual(classify_price_correction(row)["classification"], "NOT_CORRECTABLE_V1")
        with self.assertRaisesRegex(CorrectionError, "Арифмет"):
            build_correction_preview(
                row,
                {"quantity_unit": "piece", "package_size": "400", "package_unit": "g"},
            )

    def test_manual_correction_does_not_bypass_parser_contamination_guard(self):
        row = price_row(name="Čeks Jogurts 400g", normalized_name="čeks jogurts 400g")

        self.assertEqual(classify_price_correction(row)["classification"], "NOT_CORRECTABLE_V1")
        with self.assertRaisesRegex(CorrectionError, "Parser"):
            build_correction_preview(
                row,
                {"quantity_unit": "piece", "package_size": "400", "package_unit": "g"},
            )


if __name__ == "__main__":
    unittest.main()
