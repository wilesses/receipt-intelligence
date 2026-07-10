import unittest

from app.product_normalizer import extract_product_features, normalize_product_name


class ProductNormalizerTests(unittest.TestCase):
    def test_same_sku_normalizes_equally(self):
        self.assertEqual(
            normalize_product_name("GRIMBERGEN Blonde 6,7% 0,5L"),
            normalize_product_name("GRIMBERGEN Blonde 6.7% 500 ml"),
        )

    def test_examples(self):
        self.assertEqual(
            normalize_product_name("Alus GRIMBERGEN Blonde 6,7% 0,5L sk. D"),
            "alus grimbergen blonde 6.7% 500ml",
        )
        self.assertEqual(
            normalize_product_name("Coca-Cola Zero 1 L PET"),
            "coca cola zero 1000ml",
        )
        self.assertEqual(
            normalize_product_name("Coca-Cola Original 1 L PET"),
            "coca cola original 1000ml",
        )

    def test_features(self):
        self.assertEqual(
            extract_product_features(normalize_product_name("blue moon 5,4% 0.33l")),
            {"volume_ml": 330, "weight_g": None, "percentage": 5.4},
        )
        self.assertEqual(
            extract_product_features(normalize_product_name("Siers 0.5 kg")),
            {"volume_ml": None, "weight_g": 500, "percentage": None},
        )
        self.assertEqual(
            extract_product_features(normalize_product_name("Siers 500g")),
            {"volume_ml": None, "weight_g": 500, "percentage": None},
        )
        self.assertEqual(extract_product_features(normalize_product_name("Piens 2,0%"))["percentage"], 2.0)
        self.assertEqual(extract_product_features(normalize_product_name("Piens 3,5%"))["percentage"], 3.5)


if __name__ == "__main__":
    unittest.main()
