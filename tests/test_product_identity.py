import sqlite3
import unittest

from app.category_rules import get_product_key
from app.product_identity import (
    effective_product_identity,
    effective_product_identity_from_row,
    effective_product_identity_sql,
)


class EffectiveProductIdentityTests(unittest.TestCase):
    def test_raw_name_remains_identity_when_only_normalized_name_is_present(self):
        row = {
            "name": "Milk 1 L",
            "normalized_name": "milk 1l",
            "canonical_name": None,
        }

        self.assertEqual(effective_product_identity_from_row(row), "Milk 1 L")
        self.assertEqual(
            effective_product_identity("Milk 1 L", canonical_name=None),
            "Milk 1 L",
        )

    def test_canonical_name_is_authoritative_and_blank_canonical_is_safe(self):
        self.assertEqual(
            effective_product_identity("Raw alias", canonical_name="Shared product"),
            "Shared product",
        )
        self.assertEqual(
            effective_product_identity("Raw alias", canonical_name=""),
            "Raw alias",
        )
        self.assertEqual(
            effective_product_identity("Raw alias", canonical_name="   "),
            "Raw alias",
        )

    def test_sql_contract_keeps_equal_normalized_names_distinct_until_canonical_merge(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute(
            "CREATE TABLE items (name TEXT, normalized_name TEXT, canonical_name TEXT)"
        )
        conn.executemany(
            "INSERT INTO items VALUES (?, ?, ?)",
            [
                ("Milk 1 L", "milk 1l", None),
                ("MILK 1L", "milk 1l", None),
            ],
        )
        expression = effective_product_identity_sql("items")

        before = conn.execute(
            f"SELECT COUNT(DISTINCT {expression}) FROM items"
        ).fetchone()[0]
        conn.execute("UPDATE items SET canonical_name = 'Milk canonical'")
        after = conn.execute(
            f"SELECT COUNT(DISTINCT {expression}) FROM items"
        ).fetchone()[0]

        self.assertEqual(before, 2)
        self.assertEqual(after, 1)

    def test_category_rule_key_is_intentionally_not_effective_identity(self):
        raw_name = "Milk 1 L"
        normalized_name = "milk 1l"

        self.assertEqual(
            effective_product_identity(raw_name, canonical_name=None),
            raw_name,
        )
        self.assertEqual(
            get_product_key(raw_name, normalized_name, canonical_name=None),
            normalized_name,
        )


if __name__ == "__main__":
    unittest.main()
