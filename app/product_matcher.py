from collections import defaultdict
from time import monotonic
import re

from rapidfuzz import fuzz

from app.product_normalizer import extract_product_features, normalize_product_name


HIGH_CONFIDENCE_SCORE = 95.0
POSSIBLE_CONFIDENCE_SCORE = 88.0
PERCENTAGE_TOLERANCE = 0.05
PRODUCT_NAME_EXPR = "COALESCE(NULLIF(items.canonical_name, ''), items.name)"
SIGNIFICANT_TOKEN_RE = re.compile(r"\b(?!\d+(?:ml|g|gab)?\b)(?!\d+(?:\.\d+)?%\b)[a-zāčēģīķļņōŗšūž]{2,}\b")
VARIANT_TOKENS = {
    "zero", "original", "classic", "light", "blonde", "dark", "bacon",
    "cheese", "sweet", "spicy", "mild", "vanilla", "chocolate",
}
CACHE_TTL_SECONDS = 30
_cache = {}


def _tokens(value: str) -> set[str]:
    return set(SIGNIFICANT_TOKEN_RE.findall(value or ""))


def _variant_tokens(value: str) -> set[str]:
    return _tokens(value) & VARIANT_TOKENS


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
        products.append({
            "original_name": row[0],
            "normalized_name": normalized,
            "display_name": row[2],
            "item_count": int(row[3] or 0),
            "receipt_count": int(row[4] or 0),
            "category": row[5],
            "tokens": _tokens(normalized),
            "features": extract_product_features(normalized),
        })
    return products


def _blocked(left: dict, right: dict) -> bool:
    left_features = left["features"]
    right_features = right["features"]

    for key in ("volume_ml", "weight_g"):
        if left_features[key] and right_features[key] and left_features[key] != right_features[key]:
            return True

    left_percentage = left_features["percentage"]
    right_percentage = right_features["percentage"]
    if left_percentage is not None and right_percentage is not None:
        if abs(left_percentage - right_percentage) > PERCENTAGE_TOLERANCE:
            return True

    left_variants = _variant_tokens(left["normalized_name"])
    right_variants = _variant_tokens(right["normalized_name"])
    if left_variants and right_variants and left_variants != right_variants:
        return True

    return False


def _candidate_pairs(products: list[dict]):
    buckets = defaultdict(list)
    for index, product in enumerate(products):
        for token in sorted(product["tokens"])[:4]:
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


def _reasons(left: dict, right: dict, score: float, shared_features: dict) -> list[str]:
    reasons = [f"похожесть названия {round(score)}%"]
    if shared_features["volume_ml"]:
        reasons.append(f"совпадает объем {shared_features['volume_ml']} ml")
    if shared_features["weight_g"]:
        reasons.append(f"совпадает масса {shared_features['weight_g']} g")
    if shared_features["percentage"] is not None:
        reasons.append(f"совпадает крепость {shared_features['percentage']}%")
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

        score = float(fuzz.token_set_ratio(left["normalized_name"], right["normalized_name"]))
        if score < POSSIBLE_CONFIDENCE_SCORE:
            continue

        shared = _shared_features(left["features"], right["features"])
        suggestions.append({
            "left_name": left["display_name"],
            "right_name": right["display_name"],
            "left_normalized": left["normalized_name"],
            "right_normalized": right["normalized_name"],
            "score": round(score, 2),
            "confidence": "high" if score >= HIGH_CONFIDENCE_SCORE else "possible",
            "left_count": left["item_count"],
            "right_count": right["item_count"],
            "left_receipt_count": left["receipt_count"],
            "right_receipt_count": right["receipt_count"],
            "left_category": left["category"],
            "right_category": right["category"],
            "features": shared,
            "reasons": _reasons(left, right, score, shared),
            "merge_query": _merge_query(left["display_name"], right["display_name"]),
        })

    suggestions.sort(key=lambda item: (-item["score"], -item["left_count"] - item["right_count"]))
    result = suggestions[:limit]
    _cache[cache_key] = (now, result)
    return result
