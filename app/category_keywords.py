import re


CANONICAL_CATEGORIES = [
    "овощи и фрукты",
    "мясо и птица",
    "рыба и морепродукты",
    "молочные продукты и альтернативы",
    "яйца",
    "хлеб и выпечка",
    "бакалея и основные продукты",
    "готовая еда и быстрое приготовление",
    "замороженные продукты",
    "соусы, приправы и консервы",
    "снеки и сладости",
    "безалкогольные напитки",
    "алкоголь",
    "детское",
    "товары для животных",
    "бытовое и личный уход",
    "служебные строки",
    "прочее / требует решения",
]

CATEGORY_OPTIONS = CANONICAL_CATEGORIES

UNRESOLVED_CATEGORY = "прочее / требует решения"

CATEGORY_ALIASES = {
    "служебные расходы": "служебные строки",
    "мясо": "мясо и птица",
    "молочные": "молочные продукты и альтернативы",
    "молочка": "молочные продукты и альтернативы",
    "овощи": "овощи и фрукты",
    "фрукты": "овощи и фрукты",
    "выпечка": "хлеб и выпечка",
    "сладости/снеки": "снеки и сладости",
    "сладости": "снеки и сладости",
    "чай/кофе": "безалкогольные напитки",
    "напитки": "безалкогольные напитки",
    "бытовое": "бытовое и личный уход",
    "одежда": "бытовое и личный уход",
    "аптека": "бытовое и личный уход",
    "корма": "товары для животных",
    "кот": "товары для животных",
    "ребенок": "детское",
    "быстрое питание": "готовая еда и быстрое приготовление",
    "прочее": UNRESOLVED_CATEGORY,
}

LEGACY_CATEGORY_LABELS = frozenset(CATEGORY_ALIASES)

CATEGORY_SOURCES = {"rule", "manual", "inherited", "fallback"}

SOURCE_LABELS = {
    "rule": "По правилу",
    "manual": "Ручная",
    "inherited": "Унаследована",
    "fallback": "Требует решения",
}


# `*` means token prefix. Other values match one token or one whole phrase.
CATEGORY_KEYWORDS = {
    "служебные строки": [
        "depozīta maksa", "depozita maksa", "iepirkumu maisiņ*", "iepirkumu maisin*",
        "papīra maisiņ*", "papira maisin*", "iepirkumu soma",
    ],
    "товары для животных": [
        "kaķiem", "kakiem", "kaķu", "kaku", "suņiem", "suniem", "suņu", "sunu",
        "whiskas", "friskies", "perfecto", "josi",
    ],
    "детское": [
        "zīdaiņ*", "zidain*", "bērnu pārtika", "bernu partika", "mānekl*", "manekl*",
        "autiņ*", "autin*",
    ],
    "бытовое и личный уход": [
        "zobu pasta", "zobu birst*", "papīra dvieļ*", "papīra dviel*", "papira dviel*", "tualetes papīr*", "tualetes papir*",
        "dušas*", "dusas*", "šampūn*", "sampun*", "ziepes",
        "tīrīš*", "tiris*", "mazgāšan*", "mazgasan*", "dezinfekc*", "atkritumu mais*",
        "salvet*", "tampon*", "baterij*", "sveces", "apavi", "čības", "cibas",
        "skrubi*", "matu maska", "sejas*", "ķermeņa*", "kermena*", "cimdi", "tual tīr*",
    ],
    "алкоголь": [
        "alus", "sidrs", "cidrs", "vīns", "vins", "šampaniet*", "sampaniet*",
        "lager", "ipa", "beer", "spirits", "degvīn*", "degvie*", "viskij*", "rums",
    ],
    "соусы, приправы и консервы": [
        "tomātu pasta", "tomatu pasta", "mērce*", "merce*", "majonēz*", "majonez*",
        "kečup*", "kecup*", "ketchup", "sinep*", "konserv*", "srirača", "sriraca",
        "sojas mērce", "sojas merce", "tomātu biezen*", "tomatu biezen*",
    ],
    "безалкогольные напитки": [
        "tēja", "teja", "kafij*", "kakao", "oolong", "earl grey", "cappuccino",
        "ūdens", "udens", "minerālūden*", "mineraluden*", "sula", "dzērien*", "dzerien*",
        "dzérien*", "gāzēt*", "gazet*", "limonād*", "limonad*", "enerģ*", "energ*",
        "gāz dz", "gaz dz", "kola", "cola", "pepsi", "sprite", "fanta", "tonic", "kvass", "kombucha",
    ],
    "готовая еда и быстрое приготовление": [
        "ramyun", "instant", "nūd zupa", "nud zupa", "ā p nūd*", "a p nud*", "ātri pagatavojam*",
        "atri pagatavojam*", "rasols", "sviestmaiz*", "burger*", "gatavā maltīte",
        "sviestm", "salāti ar", "salat ar", "gatava maltite", "gatavs ēdiens", "gatavs ediens", "pica", "lazanja", "lasagna",
        "tortellini", "gnocchi", "zupa",
    ],
    "рыба и морепродукты": [
        "tunziv*", "ziv*", "laša", "lasa", "lasis", "garnel*", "heka", "siļķ*", "silk*",
        "forel*", "menca", "jūras veltes", "juras veltes",
    ],
    "замороженные продукты": [
        "saldēt*", "saldet*", "saldējum*", "saldejum*", "sorbet*", "frozen", "pelmeņ*", "pelmen*",
    ],
    "яйца": [
        "ola", "olas", "olu",
    ],
    "мясо и птица": [
        "cūkgaļ*", "cukgal*", "liellop*", "cāļ*", "cal*", "vist*", "šķiņķ*", "skink*",
        "gaļ*", "vistas gala", "liellopa gala", "cukas gala", "doktordes*", "cepamdes*", "desiņ*", "desin*", "desa", "desas",
        "cīsiņ*", "cisin*", "bekon*", "karbonād*", "karbonad*", "steik*", "jerky", "beef",
        "ribiņ*", "ribin*", "šnicel*", "snicel*", "sardel*", "kotlet*",
    ],
    "хлеб и выпечка": [
        "maize", "baltmaiz*", "lielmaiz*", "tostermaiz*", "rupjmaiz*", "maizīt*", "maizit*",
        "kruasān*", "kruasan*", "bulciņ*", "bulcin*",
        "virtul*", "pīrāg*", "pirag*", "pīrādziņ*", "piradzin*", "kliņģer*", "klinger*",
        "tortilj*", "kūka", "kuka", "torte", "konditorej*",
    ],
    "снеки и сладости": [
        "čips*", "cips*", "šokolād*", "sokolad*", "konfekt*", "popkorn*", "kreker*",
        "galetes", "vafeļ*", "vafel*", "zefīr*", "zefir*", "karamel*", "marshmallow",
        "baton*", "grauzdiņ*", "grauzdin*", "rieksti", "rieksts", "zemesriekst*", "sēkliņ*", "seklin*",
        "košļ*", "kosl*", "kraukšķ*", "krauksk*",
    ],
    "молочные продукты и альтернативы": [
        "piens", "piena", "jog*", "kefīr*", "kefir*", "siers", "siera", "sieriņ*", "sierin*",
        "biezpien*", "biezp*", "skābpien*", "skapien*", "piena dzērien*", "piena dzerien*",
        "paniņ*", "panin*", "krējums", "krejums", "sviests", "actimel",
    ],
    "бакалея и основные продукты": [
        "pasta", "makaroni", "nūdeles", "nudeles", "spageti", "spaghetti", "tagliatelle", "rīsi", "risi",
        "griķ*", "grik*", "auzu", "pārsl*", "parsl*", "milti", "cukurs", "eļļa", "ella",
        "putra", "lēcas", "lecas", "aunazirņ*", "aunazirn*", "pupiņ*", "pupin*", "zirņ*", "zirn*",
    ],
    "овощи и фрукты": [
        "burkān*", "burkan*", "sparģeļ*", "spargel*", "šampinjon*", "sampinjon*", "kartupeļ*",
        "kartupel*", "avokado", "kukurūz*", "kukuruz*", "zaļum*", "zalum*", "salāt*", "salat*",
        "lociņ*", "locin*", "sīpol*", "sipol*", "ķiplok*", "kiplok*", "kāpost*", "kapost*",
        "dārzeņ*", "darzen*", "tomāt*", "tomat*", "gurķ*", "gurk*", "paprik*", "ķirb*", "kirb*",
        "baklažān*", "baklazan*", "brokoļ*", "brokol*", "spināt*", "spinat*", "dill*", "selerij*",
        "cukini", "ingver*", "ābol*", "abol*", "banān*", "banan*", "vīnog*", "vinog*", "persik*",
        "mango", "apelsīn*", "apelsin*", "bumbier*", "citrons", "augļ*", "augl*", "zemen*",
        "mellen*", "aveņ*", "aven*", "kivi", "granātābol*", "granatabol*", "ananas*", "plūm*",
        "plum*", "ķirš*", "kirs*", "laimi", "arbūz*", "arbuz*", "melon*",
    ],
}


# Fixed tie order. Narrow conjunctions and the meat/dairy first-type rule below
# resolve collisions that cannot be expressed by one keyword alone.
PRIORITY = [
    "служебные строки",
    "товары для животных",
    "детское",
    "бытовое и личный уход",
    "алкоголь",
    "соусы, приправы и консервы",
    "готовая еда и быстрое приготовление",
    "рыба и морепродукты",
    "замороженные продукты",
    "яйца",
    "хлеб и выпечка",
    "снеки и сладости",
    "безалкогольные напитки",
    "мясо и птица",
    "молочные продукты и альтернативы",
    "бакалея и основные продукты",
    "овощи и фрукты",
]


def normalize_category_name(category: str | None) -> str:
    if not category or not str(category).strip():
        return UNRESOLVED_CATEGORY

    value = str(category).strip().lower()
    return CATEGORY_ALIASES.get(value, value)


def category_for_reporting(category: str | None) -> str:
    if not category or not str(category).strip():
        return UNRESOLVED_CATEGORY
    value = str(category).strip().lower()
    if value in CANONICAL_CATEGORIES:
        return value
    if value in LEGACY_CATEGORY_LABELS:
        return UNRESOLVED_CATEGORY
    return value


def _normalize_classifier_text(value: str) -> str:
    return " ".join("".join(char if char.isalpha() else " " for char in (value or "").lower()).split())


def _keyword_matches(text: str, tokens: tuple[str, ...], keyword: str) -> bool:
    is_prefix = keyword.endswith("*")
    normalized_keyword = _normalize_classifier_text(keyword[:-1] if is_prefix else keyword)
    if not normalized_keyword:
        return False
    if is_prefix:
        parts = normalized_keyword.split()
        if len(parts) == 1:
            return any(token.startswith(parts[0]) for token in tokens)
        width = len(parts)
        return any(
            tuple(tokens[index:index + width - 1]) == tuple(parts[:-1])
            and tokens[index + width - 1].startswith(parts[-1])
            for index in range(len(tokens) - width + 1)
        )
    if " " in normalized_keyword:
        return f" {normalized_keyword} " in f" {text} "
    return normalized_keyword in tokens


def score_keyword_matches(name: str) -> dict[str, int]:
    text = _normalize_classifier_text(name)
    tokens = tuple(text.split())
    return {
        category: sum(_keyword_matches(text, tokens, keyword) for keyword in keywords)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }


def _first_keyword_position(name: str, category: str) -> int:
    tokens = tuple(_normalize_classifier_text(name).split())
    positions = []
    for keyword in CATEGORY_KEYWORDS[category]:
        is_prefix = keyword.endswith("*")
        parts = tuple(_normalize_classifier_text(keyword[:-1] if is_prefix else keyword).split())
        for index in range(len(tokens) - len(parts) + 1):
            candidate = tokens[index:index + len(parts)]
            if not parts:
                continue
            if is_prefix:
                matches = candidate[:-1] == parts[:-1] and candidate[-1].startswith(parts[-1])
            else:
                matches = candidate == parts
            if matches:
                positions.append(index)
    return min(positions, default=len(tokens) + 1)


def _add_conjunctive_evidence(name: str, scores: dict[str, int]) -> None:
    text = _normalize_classifier_text(name)
    tokens = tuple(text.split())

    has_baby_age = bool(re.search(r"(?<!\d)\d{1,2}\s*\+", name or ""))
    has_baby_form = any(token.startswith(("biez", "putr", "pire")) for token in tokens)
    if has_baby_age and has_baby_form:
        scores["детское"] += 1

    has_fries = "frī" in tokens or "fri" in tokens
    has_potato = any(token.startswith(("kartupeļ", "kartupel", "kartup")) for token in tokens)
    if has_fries and has_potato:
        scores["замороженные продукты"] += 1

    has_noodles = any(token.startswith(("nūd", "nud")) for token in tokens)
    has_instant_form = any(token in {"zupa", "ramyun", "instant"} for token in tokens)
    if has_noodles and has_instant_form:
        scores["готовая еда и быстрое приготовление"] += 1

    has_bag = any(token.startswith(("maisiņ", "maisin")) for token in tokens)
    has_refuse = any(token.startswith("atkritum") for token in tokens)
    if has_bag and not has_refuse:
        scores["служебные строки"] += 1

    has_burger_bun = any(token.startswith("burgeru") for token in tokens) and any(
        "maiz" in token for token in tokens
    )
    if has_burger_bun:
        scores["готовая еда и быстрое приготовление"] = 0


def _prefer_earlier_type(name: str, scores: dict[str, int], first: str, second: str) -> None:
    if not scores[first] or not scores[second]:
        return
    if _first_keyword_position(name, first) <= _first_keyword_position(name, second):
        scores[second] = 0
    else:
        scores[first] = 0


def _must_fail_closed(name: str, scores: dict[str, int]) -> bool:
    tokens = tuple(_normalize_classifier_text(name).split())
    if "hortex" in tokens and not scores["замороженные продукты"]:
        return True
    if any(token.startswith("humoss") for token in tokens) and not scores["соусы, приправы и консервы"]:
        return True
    if any(token.startswith("kuskus") for token in tokens) and not scores["готовая еда и быстрое приготовление"]:
        return True
    is_cooked = any(token.startswith(("vārīt", "varit")) for token in tokens)
    if is_cooked and scores["овощи и фрукты"] and not scores["готовая еда и быстрое приготовление"]:
        return True
    has_salad = any(token.startswith(("salāt", "salat")) for token in tokens)
    explicit_sauce_form = any(
        token.startswith(("mērc", "merc", "majon", "kečup", "kecup", "konserv"))
        for token in tokens
    ) or "tomātu pasta" in _normalize_classifier_text(name) or "tomatu pasta" in _normalize_classifier_text(name)
    if has_salad and scores["соусы, приправы и консервы"] and not explicit_sauce_form:
        return True
    if any(token.startswith(("pankūk", "pankuk")) for token in tokens):
        return True
    if "uzkoda" in tokens and scores["молочные продукты и альтернативы"] and not scores["снеки и сладости"]:
        return True
    if "pulveris" in tokens and scores["овощи и фрукты"] and not scores["безалкогольные напитки"]:
        return True
    return False


def categorize_from_name(name: str) -> str:
    scores = score_keyword_matches(name)
    _add_conjunctive_evidence(name, scores)

    if _must_fail_closed(name, scores):
        return UNRESOLVED_CATEGORY

    meat = "мясо и птица"
    dairy = "молочные продукты и альтернативы"
    snacks = "снеки и сладости"
    beverages = "безалкогольные напитки"
    bakery = "хлеб и выпечка"
    _prefer_earlier_type(name, scores, meat, dairy)
    _prefer_earlier_type(name, scores, meat, bakery)
    _prefer_earlier_type(name, scores, snacks, dairy)
    _prefer_earlier_type(name, scores, beverages, dairy)

    for category in PRIORITY:
        if scores[category]:
            return category
    return UNRESOLVED_CATEGORY


def categorize_with_source(name: str) -> tuple[str, str]:
    category = categorize_from_name(name)
    if category == UNRESOLVED_CATEGORY:
        return category, "fallback"
    return category, "rule"
