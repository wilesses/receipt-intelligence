from collections import defaultdict
from time import monotonic
import re
import unicodedata

from rapidfuzz import fuzz

from app.product_identity import effective_product_identity_sql
from app.product_normalizer import extract_product_features, normalize_product_name


HIGH_CONFIDENCE_SCORE = 95.0
POSSIBLE_CONFIDENCE_SCORE = 88.0
PERCENTAGE_TOLERANCE = 0.05
PRODUCT_NAME_EXPR = effective_product_identity_sql("items")
SIGNIFICANT_TOKEN_RE = re.compile(r"\b(?!\d+(?:ml|g|gab)?\b)(?!\d+(?:\.\d+)?%\b)[a-zāčēģīķļņōŗšūž]{2,}\b")
VARIANT_ALIASES = {
    "zero": "zero",
    "original": "original",
    "classic": "classic",
    "light": "light",
    "blonde": "blonde",
    "dark": "dark",
    "max": "max",
    "lime": "lime",
    "laims": "lime",
    "bacon": "bacon",
    "bekona": "bacon",
    "cheese": "cheese",
    "siera": "cheese",
    "sweet": "sweet",
    "spicy": "spicy",
    "asa": "spicy",
    "aso": "spicy",
    "mild": "mild",
    "vanilla": "vanilla",
    "van": "vanilla",
    "chocolate": "chocolate",
    "sok": "chocolate",
    "karamelu": "caramel",
    "mellenu": "blueberry",
    "zem": "strawberry",
    "zemenu": "strawberry",
    "vistas": "chicken",
    "liellopu": "beef",
    "jaunie": "young",
}
VARIANT_TOKENS = set(VARIANT_ALIASES)
MULTIPACK_RE = re.compile(
    r"(?<!\d)(?P<count>\d+)\s*[xх×]\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>gab|ml|kg|gr|g|l)\b",
    re.IGNORECASE,
)
CACHE_TTL_SECONDS = 30
_cache = {}


def _tokens(value: str) -> set[str]:
    return set(SIGNIFICANT_TOKEN_RE.findall(value or ""))


def _fold_diacritics(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(char)
    )


def _comparison_name(value: str) -> str:
    return normalize_product_name(_fold_diacritics(value))


def _variant_tokens(value: str, original_name: str = "") -> set[str]:
    variants = {
        VARIANT_ALIASES[token]
        for token in _tokens(value)
        if token in VARIANT_ALIASES
    }
    if re.search(r"\bl\s+l\s+galu\b", value or ""):
        variants.add("beef")
    folded_original = _fold_diacritics(original_name).lower()
    grade = re.search(r"\b(\d+)\s*\.\s*sk\.?\b", folded_original)
    if grade:
        variants.add(f"quality-grade:{grade.group(1)}")
    egg_size = re.search(r"\b([lm])\s*\.?\s*izm\.?\b", folded_original)
    if egg_size:
        variants.add(f"egg-size:{egg_size.group(1)}")
    caliber = re.search(r"\b(\d+)\+\s*(?:mm|mu)\b", folded_original)
    if caliber:
        variants.add(f"caliber:{caliber.group(1)}")
    return variants


def _multipack_signature(value: str) -> tuple[int, int, str] | None:
    match = MULTIPACK_RE.search(value or "")
    if not match:
        return None

    count = int(match.group("count"))
    size = float(match.group("value").replace(",", "."))
    unit = match.group("unit").lower()
    if unit == "l":
        size *= 1000
        unit = "ml"
    elif unit == "kg":
        size *= 1000
        unit = "g"
    elif unit == "gr":
        unit = "g"
    return count, round(size), unit


def _load_products(conn, query: str | None, limit: int) -> list[dict]:
    params = []
    where = ""
    if query:
        normalized_query = normalize_product_name(query)
        where = f"""
            WHERE ({PRODUCT_NAME_EXPR} LIKE ?
               OR items.name LIKE ?
               OR items.normalized_name LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%", f"%{normalized_query}%"]

    rows = conn.execute(f"""
        SELECT items.name AS original_name,
               COALESCE(NULLIF(items.normalized_name, ''), '') AS normalized_name,
               {PRODUCT_NAME_EXPR} AS display_name,
               COUNT(*) AS item_count,
               COUNT(DISTINCT items.receipt_id) AS receipt_count,
               MIN(NULLIF(items.category, '')) AS category
        FROM items
        {where}
        GROUP BY items.name, items.normalized_name, display_name, items.category
        ORDER BY item_count DESC, LOWER(display_name)
        LIMIT ?
    """, [*params, max(limit * 8, 200)]).fetchall()

    products = []
    for row in rows:
        normalized = row[1] or normalize_product_name(row[0])
        if not normalized:
            continue
        comparison_name = _comparison_name(row[0]) or normalized
        products.append({
            "original_name": row[0],
            "normalized_name": normalized,
            "comparison_name": comparison_name,
            "display_name": row[2],
            "item_count": int(row[3] or 0),
            "receipt_count": int(row[4] or 0),
            "category": row[5],
            "tokens": _tokens(normalized),
            "match_tokens": _tokens(comparison_name),
            "features": extract_product_features(normalized),
            "multipack": _multipack_signature(row[0]),
            "variants": _variant_tokens(comparison_name, row[0]),
        })
    return products


def _blocked(left: dict, right: dict) -> bool:
    left_multipack = left["multipack"]
    right_multipack = right["multipack"]
    if (left_multipack is None) != (right_multipack is None):
        return True
    if left_multipack and left_multipack != right_multipack:
        return True

    left_features = left["features"]
    right_features = right["features"]

    left_measurements = {
        key for key in ("volume_ml", "weight_g") if left_features[key] is not None
    }
    right_measurements = {
        key for key in ("volume_ml", "weight_g") if right_features[key] is not None
    }
    if left_measurements and right_measurements and left_measurements.isdisjoint(right_measurements):
        return True

    for key in ("volume_ml", "weight_g"):
        if left_features[key] and right_features[key] and left_features[key] != right_features[key]:
            return True

    left_percentage = left_features["percentage"]
    right_percentage = right_features["percentage"]
    if left_percentage is not None and right_percentage is not None:
        if abs(left_percentage - right_percentage) > PERCENTAGE_TOLERANCE:
            return True

    if left["variants"] != right["variants"]:
        return True

    return False


def _candidate_pairs(products: list[dict]):
    buckets = defaultdict(list)
    for index, product in enumerate(products):
        for token in sorted(product["match_tokens"])[:4]:
            buckets[token].append(index)

    seen = set()
    for indexes in buckets.values():
        if len(indexes) > 80:
            indexes = indexes[:80]
        for pos, left_index in enumerate(indexes):
            for right_index in indexes[pos + 1:]:
                pair = tuple(sorted((left_index, right_index)))
                if pair in seen:
                    continue
                seen.add(pair)
                yield pair


def _shared_features(left_features: dict, right_features: dict) -> dict:
    return {
        key: left_features[key] if left_features[key] == right_features[key] else None
        for key in ("volume_ml", "weight_g", "percentage")
    }


def _text_similarity(left: dict, right: dict) -> tuple[float, float, float]:
    token_set_score = float(fuzz.token_set_ratio(left["comparison_name"], right["comparison_name"]))
    symmetric_score = float(fuzz.token_sort_ratio(left["comparison_name"], right["comparison_name"]))
    score = (token_set_score + symmetric_score) / 2
    return score, token_set_score, symmetric_score


def _reasons(
    left: dict,
    right: dict,
    score: float,
    symmetric_score: float,
    shared_features: dict,
) -> list[str]:
    reasons = [f"похожесть названия {round(score)}%"]
    reasons.append(f"симметричное совпадение полного названия {round(symmetric_score)}%")
    if left["match_tokens"] != right["match_tokens"]:
        reasons.append("есть несовпадающие значимые слова")
    if shared_features["volume_ml"]:
        reasons.append(f"совпадает объем {shared_features['volume_ml']} ml")
    if shared_features["weight_g"]:
        reasons.append(f"совпадает масса {shared_features['weight_g']} g")
    if shared_features["percentage"] is not None:
        reasons.append(f"совпадает крепость {shared_features['percentage']}%")
    if left["multipack"] and left["multipack"] == right["multipack"]:
        count, size, unit = left["multipack"]
        reasons.append(f"совпадает упаковка {count} × {size} {unit}")
    if left["category"] and left["category"] == right["category"]:
        reasons.append("категории совпадают")
    return reasons


def _merge_query(left_name: str, right_name: str) -> str:
    left_tokens = _tokens(normalize_product_name(left_name))
    right_tokens = _tokens(normalize_product_name(right_name))
    common = [token for token in left_tokens & right_tokens if token not in VARIANT_TOKENS]
    return common[0] if common else left_name.split()[0]


def find_similar_products(conn, query=None, limit=100) -> list[dict]:
    cache_key = (query or "", int(limit))
    cached = _cache.get(cache_key)
    now = monotonic()
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    products = _load_products(conn, query, limit)
    suggestions = []

    for left_index, right_index in _candidate_pairs(products):
        left = products[left_index]
        right = products[right_index]
        if left["normalized_name"] == right["normalized_name"] and left["display_name"] == right["display_name"]:
            continue
        if _blocked(left, right):
            continue

        score, _token_set_score, symmetric_score = _text_similarity(left, right)
        if score < POSSIBLE_CONFIDENCE_SCORE:
            continue

        shared = _shared_features(left["features"], right["features"])
        symmetric_tokens = left["match_tokens"] == right["match_tokens"]
        suggestions.append({
            "left_name": left["display_name"],
            "right_name": right["display_name"],
            "left_normalized": left["normalized_name"],
            "right_normalized": right["normalized_name"],
            "score": round(score, 2),
            "confidence": "high" if score >= HIGH_CONFIDENCE_SCORE and symmetric_tokens else "possible",
            "left_count": left["item_count"],
            "right_count": right["item_count"],
            "left_receipt_count": left["receipt_count"],
            "right_receipt_count": right["receipt_count"],
            "left_category": left["category"],
            "right_category": right["category"],
            "features": shared,
            "reasons": _reasons(left, right, score, symmetric_score, shared),
            "merge_query": _merge_query(left["display_name"], right["display_name"]),
        })

    suggestions.sort(key=lambda item: (-item["score"], -item["left_count"] - item["right_count"]))
    result = suggestions[:limit]
    _cache[cache_key] = (now, result)
    return result
