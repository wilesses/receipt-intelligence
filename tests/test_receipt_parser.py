import unittest
import hashlib
import importlib
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.receipt_parser import categorize_item, parse_receipt
from app.price_model import derive_price_data


def rimi_receipt(name, price_line="1 gab X 1,99 EUR 1,99", extra_lines=None):
    lines = [
        "SIA RIMI LATVIA",
        name,
        price_line,
        *(extra_lines or []),
        "KOPĀ 1,99",
        "Laiks 2026-07-14",
    ]
    return "\n".join(lines)


def maxima_receipt(name_lines, price_line="1,99 X 1 gab. 1,99 A", extra_lines=None):
    lines = [
        "MAXIMA",
        *name_lines,
        price_line,
        *(extra_lines or []),
        "KOPĀ APMAKSAI 1,99",
        "14.07.2026",
    ]
    return "\n".join(lines)


class ReceiptParserRegressionTests(unittest.TestCase):
    def test_parser_category_delegates_to_shared_semantic_classifier(self):
        self.assertEqual(
            categorize_item("Kruasāns ar šokolādes pildījumu 60g"),
            "хлеб и выпечка",
        )

    def test_receipt_374_golden_parses_and_derives_exact_paid_semantics(self):
        fixture = Path(__file__).parent / "fixtures" / "receipt_374_maxima.txt"
        receipt = parse_receipt(fixture.read_text(encoding="utf-8"))
        derived = [
            derive_price_data(
                name=item["name"],
                quantity=item["quantity"],
                line_total=item["price"],
                unit_price=item.get("unit_price"),
                quantity_unit=item.get("quantity_unit"),
                source="parser",
            )
            for item in receipt["items"]
        ]

        expected = (
            ("Dzeramais ūdens AQUA negāzēts 5L", 1, .97, .97, 5000, "ml", .1940, "eur_per_l"),
            ("BIO biez. RŪDOLFS dārz. rīsi vista 6+ 110g", 1, 1.74, 1.74, 110, "g", 15.8182, "eur_per_kg"),
            ("BIO biez. RŪDOLFS sald. kartup. burk. 6+110g", 1, 1.48, 1.48, 110, "g", 13.4545, "eur_per_kg"),
            ("BIO biez. RŪDOLFS aprik. ban. ķirbju 6+110g", 1, 1.48, 1.48, 110, "g", 13.4545, "eur_per_kg"),
            ("Saldēti frī kartupeļi AVIKO Steak 750g", 1, 2.62, 2.62, 750, "g", 3.4933, "eur_per_kg"),
            ("Cāļa filejas šašliks Cēzara mar. RM 700g", 1, 6.83, 6.83, 700, "g", 9.7571, "eur_per_kg"),
            ("Liell. g. uzkoda Beef Jerky Classic WD 40g", 1, 2.23, 2.23, 40, "g", 55.7500, "eur_per_kg"),
            ("Vār. Doktordesa MELNAIS BARONS 400g", 1, 2.33, 2.33, 400, "g", 5.8250, "eur_per_kg"),
            ("Nūd. zupa NONGSHIM KIMCHI RAMYUN 120g", 2, 3.10, 1.55, 120, "g", 12.9167, "eur_per_kg"),
            ("Vīns ZIBOMARE Zibibbo 12% 0,75L", 1, 6.99, 6.99, 750, "ml", 9.3200, "eur_per_l"),
            ("Proteīna dzēr. PIENA SPĒKS šokolādes 460g", 1, 1.04, 1.04, 460, "g", 2.2609, "eur_per_kg"),
        )

        self.assertEqual(receipt["store"], "MAXIMA")
        self.assertEqual(receipt["date"], "2026-08-07")
        self.assertEqual(receipt["total"], 31.00)
        self.assertEqual(len(receipt["items"]), 11)
        self.assertNotIn("Papīra iepirkumu maisiņš PALDIES", [item["name"] for item in receipt["items"]])
        self.assertEqual(round(sum(item["price"] for item in receipt["items"]), 2), 30.81)
        self.assertEqual(round(sum(item["price"] for item in receipt["items"]) + .19, 2), receipt["total"])

        for item, price_data, wanted in zip(receipt["items"], derived, expected, strict=True):
            name, quantity, total, unit_price, package_size, package_unit, normalized, normalized_unit = wanted
            with self.subTest(name=name):
                self.assertEqual(item["name"], name)
                self.assertEqual(price_data.quantity, quantity)
                self.assertEqual(price_data.quantity_unit, "piece")
                self.assertEqual(price_data.line_total, total)
                self.assertEqual(price_data.unit_price, unit_price)
                self.assertEqual(price_data.package_size, package_size)
                self.assertEqual(price_data.package_unit, package_unit)
                self.assertAlmostEqual(price_data.normalized_unit_price, normalized, places=4)
                self.assertEqual(price_data.normalized_price_unit, normalized_unit)

        rudolfs = derived[1:4]
        self.assertEqual([item.package_size for item in rudolfs], [110, 110, 110])
        self.assertTrue(all(item.package_unit == "g" for item in rudolfs))

    def test_repairs_safe_decimal_whitespace_before_liter_unit(self):
        for raw, expected in (("Piens 1, 5L", "Piens 1,5L"), ("Ūdens 0, 5L", "Ūdens 0,5L")):
            with self.subTest(raw=raw):
                result = parse_receipt(rimi_receipt(raw))
                self.assertEqual(result["items"][0]["name"], expected)

    def test_receipt_header_does_not_contaminate_maxima_product_name(self):
        result = parse_receipt(maxima_receipt(["Čeks 123/456", "Piens 1L"]))
        self.assertEqual([item["name"] for item in result["items"]], ["Piens 1L"])

    def test_standalone_receipt_number_does_not_contaminate_product_name(self):
        result = parse_receipt(maxima_receipt(["123/456", "Piens 1L"]))
        self.assertEqual([item["name"] for item in result["items"]], ["Piens 1L"])

    def test_service_and_cashier_rows_are_not_products(self):
        service = parse_receipt(rimi_receipt("Papildus depozīta maksa", "1 gab X 0,10 EUR 0,10"))
        cashier = parse_receipt(maxima_receipt(["Kase Nr. 12"]))
        self.assertEqual(service["store"], "RIMI")
        self.assertEqual(service["items"], [])
        self.assertEqual(cashier["items"], [])

    def test_removed_metadata_remains_a_name_boundary(self):
        rimi = parse_receipt(
            "\n".join([
                "SIA RIMI LATVIA",
                "Iepriekšējs teksts",
                "Kase Nr. 12",
                "Piens 1L",
                "1 gab X 1,99 EUR 1,99",
            ])
        )
        maxima = parse_receipt(
            "\n".join([
                "MAXIMA",
                "Iepriekšējs teksts",
                "Kase Nr. 12",
                "Piens 1L",
                "1,99 X 1 1,99 A",
            ])
        )
        self.assertEqual(rimi["items"][0]["name"], "Piens 1L")
        self.assertEqual(maxima["items"][0]["name"], "Piens 1L")

    def test_ambiguous_ocr_unit_tokens_are_rejected_without_guessing(self):
        for name in ("Cukurs Rimi lkg", "Šampūns 350m1", "Sviests BALTAIS250g"):
            with self.subTest(name=name):
                self.assertEqual(parse_receipt(rimi_receipt(name))["items"], [])

    def test_unsafe_decimal_corruption_is_rejected(self):
        self.assertEqual(parse_receipt(rimi_receipt("Dzēriens 2, 86L"))["items"], [])

    def test_multipack_is_preserved_not_guessed(self):
        result = parse_receipt(rimi_receipt("Dzēriens 6x330ml"))
        self.assertEqual(result["items"][0]["name"], "Dzēriens 6x330ml")

    def test_normal_rimi_piece_item(self):
        result = parse_receipt(rimi_receipt("Olas 10gab", "2 gab X 2,00 EUR 4,00"))
        item = result["items"][0]
        self.assertEqual(result["date"], "2026-07-14")
        self.assertEqual((item["quantity"], item["quantity_unit"], item["unit_price"], item["price"]), (2, "gab", 2, 4))

    def test_rimi_weighted_item(self):
        result = parse_receipt(rimi_receipt("Tomāti kg", "0,5 kg X 3,00 EUR/kg 1,50"))
        item = result["items"][0]
        self.assertEqual((item["quantity"], item["quantity_unit"], item["unit_price"], item["price"]), (0.5, "kg", 3, 1.5))

    def test_rimi_discount_uses_final_price(self):
        result = parse_receipt(rimi_receipt("Siers 200g", extra_lines=["ATL. -0,50", "Gala cena 1,49"]))
        item = result["items"][0]
        data = derive_price_data(
            name=item["name"],
            quantity=item["quantity"],
            line_total=item["price"],
            unit_price=item["unit_price"],
            quantity_unit=item["quantity_unit"],
            source="parser",
        )
        self.assertEqual(item["price"], 1.49)
        self.assertEqual(data.unit_price, 1.49)
        self.assertEqual(data.normalized_unit_price, 7.45)

    def test_normal_maxima_item(self):
        result = parse_receipt(maxima_receipt(["Piens 1L"]))
        item = result["items"][0]
        self.assertEqual(result["date"], "14.07.2026")
        self.assertEqual(
            (item["name"], item["quantity"], item["quantity_unit"], item["price"]),
            ("Piens 1L", 1, "piece", 1.99),
        )

    def test_maxima_weighted_caliber_uses_fractional_merchant_evidence(self):
        result = parse_receipt(
            maxima_receipt(["Sīpoli 45+ kg 2. šķ."], price_line="0,91 X 0,580 0,53 A")
        )
        item = result["items"][0]
        data = derive_price_data(
            name=item["name"],
            quantity=item["quantity"],
            line_total=item["price"],
            unit_price=item["unit_price"],
            quantity_unit=item["quantity_unit"],
            source="parser",
        )

        self.assertEqual(item["quantity_unit"], "unknown")
        self.assertEqual(data.quantity_unit, "kg")
        self.assertEqual(data.unit_price, round(.53 / .58, 4))
        self.assertEqual(data.normalized_unit_price, round(.53 / .58, 4))

    def test_maxima_discount_uses_discount_price(self):
        result = parse_receipt(maxima_receipt(["Siers 200g"], extra_lines=["Cena ar atlaidi 1,49"]))
        self.assertEqual(result["items"][0]["price"], 1.49)


class ParserAuditTests(unittest.TestCase):
    @staticmethod
    def _create_audit_database(db_path):
        with closing(sqlite3.connect(db_path)) as conn:
            conn.execute(
                "CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, normalized_unit_price REAL)"
            )
            conn.executemany(
                "INSERT INTO items (name) VALUES (?)",
                [
                    ("Piens 1, 5L",),
                    ("Cukurs lkg",),
                    ("Čeks 1/2 Piens",),
                    ("Dzēriens 6x330ml",),
                    ("Dzēriens 6x0, 5L",),
                    ("Kase Nr. 12 1, 5L",),
                    ("Piens 1L",),
                ],
            )
            conn.commit()

    def test_module_import_has_no_database_side_effects(self):
        sys.modules.pop("app.audit_parser_quality", None)
        with patch("sqlite3.connect") as connect:
            importlib.import_module("app.audit_parser_quality")
        connect.assert_not_called()

    def test_audit_uses_immutable_read_only_connection_without_migrations(self):
        audit = importlib.import_module("app.audit_parser_quality")
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            self._create_audit_database(db_path)
            real_connect = sqlite3.connect

            with (
                patch.object(audit.sqlite3, "connect", wraps=real_connect) as connect,
                patch("app.db.create_tables", side_effect=AssertionError("migration called")),
                patch("app.db.get_connection", side_effect=AssertionError("write connection called")),
            ):
                audit.audit_database(db_path)

            uri = connect.call_args.args[0]
            self.assertIn("mode=ro", uri)
            self.assertIn("immutable=1", uri)
            self.assertTrue(connect.call_args.kwargs["uri"])

    def test_cli_classifies_rows_and_keeps_database_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            self._create_audit_database(db_path)
            from app.db import DB_PATH

            self.assertNotEqual(db_path.resolve(), DB_PATH.resolve())
            before_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
            before_stat = db_path.stat()
            wal_path = Path(str(db_path) + "-wal")
            shm_path = Path(str(db_path) + "-shm")
            self.assertFalse(wal_path.exists())
            self.assertFalse(shm_path.exists())

            completed = subprocess.run(
                [sys.executable, "-m", "app.audit_parser_quality", "--db", str(db_path), "--examples", "1"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("ocr_decimal_corruption: 2", completed.stdout)
            self.assertIn("ocr_lkg: 1", completed.stdout)
            self.assertIn("receipt_header: 1", completed.stdout)
            self.assertIn("multipack: 1", completed.stdout)
            self.assertIn("projected corrected: 1", completed.stdout)
            self.assertIn("projected rejected: 3", completed.stdout)
            self.assertIn("projected unresolved: 2", completed.stdout)
            after_stat = db_path.stat()
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), before_hash)
            self.assertEqual(after_stat.st_size, before_stat.st_size)
            self.assertEqual(after_stat.st_mtime_ns, before_stat.st_mtime_ns)
            self.assertFalse(wal_path.exists())
            self.assertFalse(shm_path.exists())


if __name__ == "__main__":
    unittest.main()
