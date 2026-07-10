import re


CATEGORY_OPTIONS = [
    "мясо",
    "молочка",
    "овощи",
    "фрукты",
    "выпечка",
    "сладости",
    "напитки",
    "чай/кофе",
    "бытовое",
    "детское",
    "аптека",
    "кот",
    "прочее",
]


CATEGORY_KEYWORDS = {
    "служебные расходы": [
        "papildus", "depozīta", "maksa", "maisiņš", "maisins", "iepirkumu", "soma",
    ],
    "овощи": [
        "burkān", "sparģeļ", "šampinjon", "kartupeļ", "avokado", "kukurūz", "zaļum", "salāt",
        "lociņ", "sīpol", "ķiplok", "kāpost", "dārzeņ", "tomāt", "gurķ", "paprik", "ķirb",
        "baklažān", "ziedkāpost", "brokoļ", "spināt", "pētersīļ", "dill", "bazilik", "koriandr",
        "piparmētr", "selerij", "purav", "redīs", "cukini", "pupiņ", "zirņ", "ingvers",
    ],
    "фрукты": [
        "ābol", "banān", "vīnog", "persik", "mango", "apelsīn", "bumbier", "citrons", "augļ",
        "zemen", "mellen", "aveņ", "kivi", "granātābol", "ananas", "aprikoz", "plūm", "ķirš",
        "laimi", "arbūz", "melone", "melones",
    ],
    "мясо": [
        "cūkgaļ", "tunziv", "cāļ", "šķiņķ", "ziv", "pusspārn", "ķekava", "liellop", "olas",
        "cepamdesas", "ribiņ", "vist", "filej", "gaļ", "šnicel", "sardel", "kotlet", "rib",
        "des", "bekon", "heka", "amerikāņu", "cīsiņ", "desiņ", "žāvēta gaļ", "saldēta gaļ",
        "karbonād", "steik", "garnel", "gril-ribas", "zivju", "asinsdesas", "doktordesa",
    ],
    "молочные": [
        "piens", "piena", "biezp", "paniņ", "kokosriekst", "saldēj", "sieriņš", "kārums",
        "krējums", "cheddar", "sviests", "siers", "kefīrs", "jogurt", "dzintars", "siera",
        "jog.", "actimel",
    ],
    "выпечка": [
        "maize", "kūka", "milti", "virtulis", "tortilj", "herkuless", "kviešu", "galetes",
        "bulciņ", "konditorej", "cepumi", "kliņģer", "maizīt", "pīrāg", "pīrādziņ", "torte",
        "kruasāns", "eļļa",
    ],
    "сладости/снеки": [
        "šokolād", "cukurs", "arimex", "snickers", "humoss", "orbit", "estrella", "vafeļ",
        "konfekt", "plombīr", "zefīr", "karamel", "marshmallow", "čips", "popkorn",
        "grauzdiņ", "kreker", "deserts", "nestle", "prot. baton.", "baton", "magnum",
    ],
    "чай/кофе": [
        "tēja", "kafij", "kakao", "oolong", "earl grey", "cappuccino", "sīrups",
    ],
    "напитки": [
        "ūdens", "sula", "gāzēt", "kola", "enerģ", "dzēriens", "minerālūdens", "limonād",
        "alus", "sprite", "fanta", "vīns", "šampaniet", "kokteil", "spirits", "pepsi",
        "cola", "sanpellegrino", "tonic", "grimbergen", "kronenburg", "kvass", "kombucha",
        "cidrs", "lager", "ipa", "beer", "tiesseire",
    ],
    "бытовое": [
        "papīrs", "spontex", "persil", "aquaphor", "libresse", "domestos", "dviel", "gilette",
        "tulpes", "dezinfekc", "baterijas", "dušas", "šampūn", "colgate", "ziepes", "tualet",
        "līdzekl", "bioderma", "dušas eļļa", "atkritum", "mazgāšan", "tīrīš", "lenor",
        "silan", "zewa", "apavu", "cerave", "pulver", "balon", "sveces", "dezinficējošs",
        "salvet", "papīra dvieļi", "šamp", "tualetes", "tampon", "bloom", "carefree",
        "naturella",
    ],
    "корма": [
        "kaķ", "suņ", "gardum", "josi", "whiskas", "friskies", "kaķiem",
    ],
    "быстрое питание": [
        "makaroni", "nūd", "griķ", "auzu", "santa maria", "santa", "santamaria", "kikkoman",
        "pica", "spilva", "majonēz", "pelmeņ", "zupa", "frī", "spaget", "ramen", "instant",
        "putra", "rīsi", "pasta", "konserv", "merce", "srirača", "konservēti", "tagliatelle",
        "lasagna", "tortellini", "gnocchi", "nūdeles", "rasols", "kartup.", "farm frites",
        "vegeta", "sojas", "jūraszāļu",
    ],
    "замороженные продукты": [
        "saldēt", "frozen", "ledus", "hortex", "sald.", "farm frites",
    ],
    "прочее": [],
}


PRIORITY = [
    "служебные расходы", "мясо", "молочные", "овощи", "фрукты", "напитки",
    "выпечка", "сладости/снеки", "чай/кофе", "корма", "быстрое питание",
    "бытовое", "замороженные продукты",
]


def categorize_from_name(name: str) -> str:
    name_clean = re.sub(r"[^a-zāčēģīķļņōŗšūž.\s]", "", name.lower())
    words = [word for word in name_clean.split() if len(word) >= 3]
    match_count = {category: 0 for category in CATEGORY_KEYWORDS}

    for word in words:
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in word or keyword in name_clean:
                    match_count[category] += 1

    if all(count == 0 for count in match_count.values()):
        return "прочее"

    max_count = max(match_count.values())
    candidates = [category for category, count in match_count.items() if count == max_count]

    for category in PRIORITY:
        if category in candidates:
            return category

    return "прочее"
