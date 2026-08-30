import unittest

import app.category_keywords as category_keywords
from app.category_keywords import (
    CANONICAL_CATEGORIES,
    UNRESOLVED_CATEGORY,
    categorize_with_source,
)


class CategoryClassifierV2Tests(unittest.TestCase):
    def test_each_keyword_scores_once_per_name(self):
        scorer = getattr(category_keywords, "score_keyword_matches", None)
        self.assertIsNotNone(scorer, "Category scorer must expose one-count-per-keyword results")

        scores = scorer("Piens extra descriptive words 2%")

        self.assertEqual(scores["молочные продукты и альтернативы"], 1)

    def test_verified_production_golden_set(self):
        cases = {
            "Kūtī dētas olas 10gab.": "яйца",
            "Liellopa maltā gaļa WELL DONE 400g": "мясо и птица",
            "Cāļa krūtiņas fileja WELL DONE 500g": "мясо и птица",
            "Vār. Doktordesa MELNAIS BARONS 400g": "мясо и птица",
            "Liell. g. uzkoda Beef Jerky Classic WD 40g": "мясо и птица",
            "Atlantijas laSa fileja kg": "рыба и морепродукты",
            "Garneles NOWACO 16-20 b/g jēlas 300g": "рыба и морепродукты",
            "Piens WELL DONE 2,0% 1L": "молочные продукты и альтернативы",
            "Jogurts GRIEĶU bez piedevām 400g": "молочные продукты и альтернативы",
            "Kausētais siers DZINTARS ar šķiņķi 200g": "молочные продукты и альтернативы",
            "Kartupeļu čipsi LAY'S siera 200g": "снеки и сладости",
            "Pasta DE CECCO Spaghetti Nr. 12 500g": "бакалея и основные продукты",
            "Tomātu pasta SPILVA 520g": "соусы, приправы и консервы",
            "Rīsi VALDO kārba 8x125g": "бакалея и основные продукты",
            "Griki Valdo 4x125g": "бакалея и основные продукты",
            "Pilngraudu auzu pārslas DOBELE 500g": "бакалея и основные продукты",
            "Kviešu milti WELL DONE 550D 2kg": "бакалея и основные продукты",
            "Saulespuķu eļļa EXTRA LINE 1L": "бакалея и основные продукты",
            "Nūd. zupa NONGSHIM KIMCHI RAMYUN 120g": "готовая еда и быстрое приготовление",
            "Saldēti frī kartupeļi AVIKO Steak 750g": "замороженные продукты",
            "Baltmaize kefīra Lielmaize LM 500g": "хлеб и выпечка",
            "Kruasāns 7DAYS ar kakao krēmu 60g": "хлеб и выпечка",
            "Salsas mērce DIP SANTA MARIA vid. as. 250g": "соусы, приправы и консервы",
            "Majonēze HELLMANNS ORIGINAL 76% 405ml": "соусы, приправы и консервы",
            "Zaļā tēja LIPTON aveņu-zemeņu 20x1,4g": "безалкогольные напитки",
            "Malta kafija LAVAZZA CLUB 250g": "безалкогольные напитки",
            "Dzeramais ūdens AQUA negāzēts 5L": "безалкогольные напитки",
            "Gāzēts dzēriens FANTA ORANGE 2L PET D": "безалкогольные напитки",
            "Energijas dzériens Monster 0,51": "безалкогольные напитки",
            "Alus MADONAS nefiltrēts 5,6% 0,5L D": "алкоголь",
            "Sidrs LIELVĀRDES CRAFT CAN 5,6% 0,5L D": "алкоголь",
            "Vīns POMEGRANATE 12,5% 0,75L": "алкоголь",
            "Konservi kaķiem JOSI liellopa 100g": "товары для животных",
            "Konservi kaķiem JOSI laša 100g": "товары для животных",
            "Zobu pasta SENSODYNE COMPL. PROTECT. 75ml": "бытовое и личный уход",
            "BIO biez. RŪDOLFS dārz. rīsi vista 6+ 110g": "детское",
            "Papildus depozīta maksa": "служебные строки",
            "Papīra iepirkumu maisiņš PALDIES": "служебные строки",
        }

        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(categorize_with_source(name), (expected, "rule"))

    def test_collision_guards_fail_closed_or_follow_product_type(self):
        cases = {
            "Coca-Cola Zero 1.5L": "безалкогольные напитки",
            "Tomātu pasta 500g": "соусы, приправы и консервы",
            "Zobu pasta 75ml": "бытовое и личный уход",
            "Čipsi ar siera garšu 130g": "снеки и сладости",
            "Tēja ar zemeņu garšu 20x1,5g": "безалкогольные напитки",
            "Konservi kaķiem ar tunci 100g": "товары для животных",
            "Produkts TEST 5,0% 500g": UNRESOLVED_CATEGORY,
            "Sald. TEST 500g": UNRESOLVED_CATEGORY,
            "Santa Maria 250g": UNRESOLVED_CATEGORY,
            "Spilva 500g": UNRESOLVED_CATEGORY,
            "Matu šampūns DZINTARS 250ml": "бытовое и личный уход",
            "Cāļa šķiņķi grieķu jog. marinādē 400g": "мясо и птица",
            "Kruasāns ar šokolādes pildījumu 60g": "хлеб и выпечка",
            "Biezpiena sieriņš KĀRUMS šokolādes 45g": "молочные продукты и альтернативы",
            "Zemesrieksti ESTRELLA Čedaras siers 140g": "снеки и сладости",
            "Āboli ROYAL GALA 75+ kg 2. šķ.": "овощи и фрукты",
            "Gāz. dz. SANPELLEGRINO Mel.&Aran. 330ml D": "безалкогольные напитки",
            "Ā/p nūdeles Carbonara SAM YANG 130g": "готовая еда и быстрое приготовление",
            "Sviestm. GIGA ar vist. g. gurķi sieru 260g": "готовая еда и быстрое приготовление",
            "Gaļas salāti ar šķiņķi 500g": "готовая еда и быстрое приготовление",
            "RAMEN nūdeles SANTA MARIA 200G": "бакалея и основные продукты",
            "Dārzeņi cepšanai HORTEX 400g": UNRESOLVED_CATEGORY,
            "Humoss ar zaļumiem ATLANTIKA 200g": UNRESOLVED_CATEGORY,
            "Kuskuss ar dārzeņiem GRACI 300g": UNRESOLVED_CATEGORY,
            "Papīra dvieļi BLOOM Comfort 2k. 500lap.": "бытовое и личный уход",
            "Dabiskā lateksa cimdi SPONTEX M": "бытовое и личный уход",
            "Zobu birste COLGATE Ultra Soft 1+1": "бытовое и личный уход",
            "Tual. tīr. līdz. DOMESTOS Lime 700ml": "бытовое и личный уход",
            "Biezp. krēms KĀRUMS ar zem., ērkš. 140g": "молочные продукты и альтернативы",
            "Skābpiena dzēriens AYRAN Baltais 500ml": "молочные продукты и альтернативы",
            "Kukurūzas saldās vālītes vārītas 450g": UNRESOLVED_CATEGORY,
            "Ledus tēja FUZETEA citr.-citronz. 1,5L D": "безалкогольные напитки",
            "Saldējums MAGNUM Mini Mix 6x42g": "замороженные продукты",
            "Burgeru maizītes Maiziņš 240g": "хлеб и выпечка",
            "Gurķu-sinepju salāti SPILVA 390g": UNRESOLVED_CATEGORY,
            "Šampinjoni 250g": "овощи и фрукты",
            "K/k cūkgaļa kubiciņos Pīrādziņu RGK 350g": "мясо и птица",
            "Pankūkas ar biezpiena pildīj. MĀJAS 420g": UNRESOLVED_CATEGORY,
            "Siera uzkoda WELL DONE PREMIUM Pizza 24g": UNRESOLVED_CATEGORY,
            "Pulveris Isostar H&P apelsinu 400g": UNRESOLVED_CATEGORY,
            "Tostermaize kefīra vērtīgā FAZER 450g": "хлеб и выпечка",
            "Ķirbis RIEKSTU kg 2. šķ.": "овощи и фрукты",
        }

        for name, expected in cases.items():
            with self.subTest(name=name):
                category, source = categorize_with_source(name)
                self.assertEqual(category, expected)
                self.assertEqual(source, "fallback" if expected == UNRESOLVED_CATEGORY else "rule")

    def test_every_result_uses_approved_vocabulary(self):
        for name in ("", "unknown", "Santa Maria", "olas", "zivju fileja", "zobu pasta"):
            with self.subTest(name=name):
                self.assertIn(categorize_with_source(name)[0], CANONICAL_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
