from collections import defaultdict
from statistics import median

from app.price_deviation import (
    PRICE_UNIT_LABELS,
    has_resolved_price_identity,
    is_eligible_price_observation,
)


def _empty_result(reason):
    return {
        "evidence_level": None,
        "reason": reason,
        "stores": [],
        "normalized_price_unit": None,
        "unit_label": None,
        "cheapest_store": None,
        "comparison_store": None,
        "difference_percent": None,
        "is_tie": False,
        "strong_claim_allowed": False,
    }


def _observation_word(count):
    if count % 10 == 1 and count % 100 != 11:
        return "покупка"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return "покупки"
    return "покупок"


def build_store_price_comparison(observations):
    """Build a fail-closed historical comparison for one effective product group."""
    rows = list(observations)
    if not rows:
        return _empty_result("insufficient_comparable_prices")
    if not has_resolved_price_identity(rows):
        return _empty_result("unresolved_product_identity")

    represented_stores = {
        str(row.get("store") or "").strip()
        for row in rows
        if str(row.get("store") or "").strip()
    }
    eligible = [row for row in rows if is_eligible_price_observation(row)]
    normalized_units = {row["normalized_price_unit"] for row in eligible}
    if len(normalized_units) > 1:
        return _empty_result("incompatible_price_units")

    prices_by_store = defaultdict(list)
    dates_by_store = defaultdict(list)
    for row in eligible:
        store = str(row["store"]).strip()
        prices_by_store[store].append(float(row["normalized_unit_price"]))
        dates_by_store[store].append(str(row["date"]))

    if len(prices_by_store) < 2:
        reason = "only_one_store" if len(represented_stores) <= 1 else "insufficient_comparable_prices"
        return _empty_result(reason)

    normalized_unit = next(iter(normalized_units))
    stores = []
    for store, prices in prices_by_store.items():
        observation_count = len(prices)
        stores.append({
            "store": store,
            "observation_count": observation_count,
            "observation_word": _observation_word(observation_count),
            "median_price": round(float(median(prices)), 4),
            "min_price": round(min(prices), 4),
            "max_price": round(max(prices), 4),
            "latest_date": max(dates_by_store[store]),
        })
    stores.sort(key=lambda store: (
        store["median_price"],
        store["store"].casefold(),
        store["store"],
    ))

    minimum_observations = min(store["observation_count"] for store in stores)
    if minimum_observations >= 3:
        evidence_level = "COMPARABLE"
    elif minimum_observations >= 2:
        evidence_level = "LIMITED"
    else:
        evidence_level = "PRELIMINARY"

    is_tie = stores[0]["median_price"] == stores[1]["median_price"]
    cheapest_store = None
    comparison_store = None
    difference_percent = None
    if evidence_level != "PRELIMINARY" and not is_tie:
        cheapest_store = stores[0]["store"]
        comparison_store = stores[1]["store"]
        comparison_median = stores[1]["median_price"]
        difference_percent = round(
            ((comparison_median - stores[0]["median_price"]) / comparison_median) * 100,
            1,
        )

    return {
        "evidence_level": evidence_level,
        "reason": None,
        "stores": stores,
        "normalized_price_unit": normalized_unit,
        "unit_label": PRICE_UNIT_LABELS[normalized_unit],
        "cheapest_store": cheapest_store,
        "comparison_store": comparison_store,
        "difference_percent": difference_percent,
        "is_tie": is_tie,
        "strong_claim_allowed": evidence_level == "COMPARABLE" and cheapest_store is not None,
    }
