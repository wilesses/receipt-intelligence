from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median

from app.price_model import MAX_REASONABLE_NORMALIZED_PRICE, derive_price_data
from app.product_identity import effective_product_identity_from_row


ELIGIBLE_PRICE_SOURCES = frozenset({
    "derived",
    "package_name",
    "parser",
    "weighted_inference",
    "manual_correction",
})
ELIGIBLE_PRICE_UNITS = frozenset({"eur_per_kg", "eur_per_l", "eur_per_piece"})
PRICE_UNIT_LABELS = {
    "eur_per_kg": "€/kg",
    "eur_per_l": "€/L",
    "eur_per_piece": "€/шт.",
}
MIN_PRICE_CONFIDENCE = Decimal("0.75")
ARITHMETIC_TOLERANCE = Decimal("0.02")
HISTORICAL_WINDOW_DAYS = 180
MIN_PRIOR_OBSERVATIONS = 3
CHEAPER_THRESHOLD = Decimal("-0.10")
EXPENSIVE_THRESHOLD = Decimal("0.15")

KNOWN_UNRESOLVED_IDENTITIES = frozenset({
    "Dilles 100g",
    "Gazéts dzér. Coca-Cola Zero ZIP paka 2x1, 51",
    "dilles 30g",
})

BLOCKING_PRICE_WARNINGS = frozenset({
    "age_package_ambiguous",
    "ambiguous_package_size",
    "invalid_package_size",
    "line_total_unit_price_mismatch",
    "multipack_unresolved",
    "normalized_unit_price_not_positive",
    "normalized_unit_price_suspicious",
    "parser_contamination",
    "service_line",
    "weighted_measurement_ambiguous",
})


def _as_decimal(value):
    try:
        if value is None or value == "":
            return None
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (ArithmeticError, InvalidOperation, ValueError):
        return None


def has_resolved_price_identity(observations):
    rows = list(observations)
    effective_names = {
        effective_product_identity_from_row(row).strip()
        for row in rows
        if effective_product_identity_from_row(row).strip()
    }
    if len(effective_names) != 1:
        return False
    if next(iter(effective_names)) in KNOWN_UNRESOLVED_IDENTITIES:
        return False
    canonical_states = {
        bool(str(row.get("canonical_name") or "").strip())
        for row in rows
    }
    return len(canonical_states) <= 1


def price_observation_ineligibility_reason(row):
    quantity = _as_decimal(row.get("quantity"))
    line_total = _as_decimal(row.get("line_total"))
    unit_price = _as_decimal(row.get("unit_price"))
    normalized_price = _as_decimal(row.get("normalized_unit_price"))
    confidence = _as_decimal(row.get("price_parse_confidence"))
    if normalized_price is None:
        return "missing_normalized_price"
    if any(value is None for value in (quantity, line_total, unit_price, confidence)):
        return "missing_price_evidence"
    if quantity <= 0 or line_total <= 0 or unit_price <= 0 or normalized_price <= 0:
        return "non_positive_price_evidence"
    if normalized_price > MAX_REASONABLE_NORMALIZED_PRICE:
        return "normalized_price_out_of_range"
    if confidence < MIN_PRICE_CONFIDENCE:
        return "low_confidence"
    if row.get("normalized_price_unit") not in ELIGIBLE_PRICE_UNITS:
        return "unsupported_unit"
    if row.get("price_parse_source") not in ELIGIBLE_PRICE_SOURCES:
        return "unsupported_source"
    if not str(row.get("store") or "").strip():
        return "missing_store"
    if not str(row.get("date") or "").strip():
        return "invalid_date"
    if abs(quantity * unit_price - line_total) > ARITHMETIC_TOLERANCE:
        return "arithmetic_mismatch"

    diagnostics = derive_price_data(
        name=row.get("name") or "",
        normalized_name=row.get("normalized_name"),
        quantity=float(quantity),
        line_total=float(line_total),
        unit_price=float(unit_price),
        quantity_unit=row.get("quantity_unit"),
        package_size=row.get("package_size"),
        package_unit=row.get("package_unit"),
        source=row.get("price_parse_source") or "derived",
    )
    warnings = BLOCKING_PRICE_WARNINGS.intersection(diagnostics.warnings)
    if "service_line" in warnings:
        return "service_line"
    if "parser_contamination" in warnings:
        return "parser_contamination"
    if "multipack_unresolved" in warnings:
        return "unresolved_multipack"
    if warnings.intersection({
        "age_package_ambiguous",
        "ambiguous_package_size",
        "invalid_package_size",
        "weighted_measurement_ambiguous",
    }):
        return "ambiguous_measurement"
    if "line_total_unit_price_mismatch" in warnings:
        return "arithmetic_mismatch"
    if warnings:
        return "blocked_price_diagnostic"
    return None


def is_eligible_price_observation(row):
    return price_observation_ineligibility_reason(row) is None


def _parsed_date(row):
    try:
        return date.fromisoformat(str(row.get("date") or ""))
    except ValueError:
        return None


def _ordering_key(row):
    try:
        return str(row.get("date") or ""), int(row["receipt_id"]), int(row["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _empty_result(current, reason, prior_count=0):
    price = _as_decimal(current.get("normalized_unit_price"))
    return {
        "status": "INSUFFICIENT_HISTORY",
        "reason": reason,
        "current_normalized_price": float(price) if price is not None else None,
        "normalized_price_unit": current.get("normalized_price_unit"),
        "historical_median": None,
        "historical_min": None,
        "historical_max": None,
        "deviation_ratio": None,
        "deviation_percent": None,
        "eligible_prior_observation_count": prior_count,
        "historical_window_days": HISTORICAL_WINDOW_DAYS,
        "evidence_strength": "INSUFFICIENT",
    }


def evaluate_price_deviation(current_observation, observations):
    """Compare one normalized price with eligible prior prices of same product/unit."""
    current = dict(current_observation)
    effective_name = effective_product_identity_from_row(current).strip()
    group = [
        row for row in observations
        if effective_product_identity_from_row(row).strip() == effective_name
    ]
    if not effective_name or not has_resolved_price_identity(group):
        return _empty_result(current, "unresolved_product_identity")

    reason = price_observation_ineligibility_reason(current)
    if reason:
        return _empty_result(current, reason)
    current_date = _parsed_date(current)
    current_key = _ordering_key(current)
    if current_date is None or current_key is None:
        return _empty_result(current, "invalid_date_or_ordering")

    window_start = current_date - timedelta(days=HISTORICAL_WINDOW_DAYS)
    unit = current["normalized_price_unit"]
    prior_prices = []
    for row in group:
        row_date = _parsed_date(row)
        row_key = _ordering_key(row)
        if (
            row_date is None
            or row_key is None
            or row_key >= current_key
            or row_date < window_start
            or row.get("normalized_price_unit") != unit
            or not is_eligible_price_observation(row)
        ):
            continue
        prior_prices.append(_as_decimal(row["normalized_unit_price"]))

    prior_count = len(prior_prices)
    if prior_count < MIN_PRIOR_OBSERVATIONS:
        return _empty_result(current, "insufficient_prior_history", prior_count)

    historical_median = median(prior_prices)
    current_price = _as_decimal(current["normalized_unit_price"])
    deviation_ratio = (current_price - historical_median) / historical_median
    if deviation_ratio <= CHEAPER_THRESHOLD:
        status = "CHEAPER_THAN_USUAL"
    elif deviation_ratio >= EXPENSIVE_THRESHOLD:
        status = "MORE_EXPENSIVE_THAN_USUAL"
    else:
        status = "NORMAL"

    return {
        "status": status,
        "reason": None,
        "current_normalized_price": float(current_price),
        "normalized_price_unit": unit,
        "historical_median": float(historical_median),
        "historical_min": float(min(prior_prices)),
        "historical_max": float(max(prior_prices)),
        "deviation_ratio": float(deviation_ratio),
        "deviation_percent": round(float(deviation_ratio * 100), 1),
        "eligible_prior_observation_count": prior_count,
        "historical_window_days": HISTORICAL_WINDOW_DAYS,
        "evidence_strength": "SUFFICIENT",
    }
