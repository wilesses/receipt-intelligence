from dataclasses import asdict, dataclass, field
import re

QUANTITY_UNITS = {"piece", "kg", "g", "l", "ml", "unknown"}
PACKAGE_UNITS = {"piece", "g", "ml", "unknown"}
NORMALIZED_UNITS = {"eur_per_l", "eur_per_kg", "eur_per_piece", "unknown"}
MAX_REASONABLE_NORMALIZED_PRICE = 10000


def is_service_line(name: str | None) -> bool:
    text = " ".join((name or "").strip().lower().split())
    patterns = (
        r"(?:papildus\s+)?depoz[iī]ta\s+maksa",
        r"(?:deposit(?:\s+fee)?|depozīts?)",
        r"(?:iepakojums|packaging)(?:\s+(?:maksa|fee))?",
        r"(?:paper|reusable|shopping)\s+bag(?:\s+\w+){0,2}",
        r"(?=.*\bmaisi(?:ņš|ns|nss)\b)(?=.*\b(?:iepirkumu|papīra|papira|rimi|lietojams|bioloģiskais|biologiskais|letaupi)\b).+",
        r"(?:kases\s+pakalpojums|cashier\s+service)(?:\s+(?:maksa|fee))?",
    )
    return any(re.fullmatch(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


@dataclass
class ParsedPriceData:
    quantity: float
    quantity_unit: str
    line_total: float
    unit_price: float | None
    package_size: float | None
    package_unit: str | None
    normalized_unit_price: float | None
    normalized_price_unit: str
    source: str
    confidence: float | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _as_float(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def normalize_quantity_unit(unit: str | None) -> str:
    value = (unit or "").strip().lower().rstrip(".")
    return {
        "gab": "piece",
        "gb": "piece",
        "pcs": "piece",
        "pc": "piece",
        "piece": "piece",
        "kg": "kg",
        "g": "g",
        "gr": "g",
        "l": "l",
        "ml": "ml",
    }.get(value, "unknown")


def extract_package_size(name: str | None, normalized_name: str | None = None) -> tuple[float | None, str | None, list[str]]:
    raw = (name or "").lower()
    unit_pattern = r"(?:kg|ml|gr|g|l|gab|gb|pcs|pc|pieces|piece)"

    if re.search(rf"\b\d+\s*[xх×]\s*\d+(?:[.,]\d+)?\s*{unit_pattern}\b", raw) or re.search(
        r"\b\d+\s*\+\s*\d+\b", raw
    ):
        return None, None, ["multipack_unresolved"]
    if re.search(rf"\d+\s*,\s+\d+\s*{unit_pattern}\b", raw) or re.search(
        rf"\d+\s*\+\s*{unit_pattern}\b", raw
    ):
        return None, None, ["ambiguous_package_size"]
    if re.search(rf"[^\W\d_]\d+(?:[.,]\d+)?\s*{unit_pattern}\b", raw):
        return None, None, ["ambiguous_package_size"]

    matches = list(re.finditer(rf"(?<![\w+])(\d+(?:[.,]\d+)?)\s*({unit_pattern})\b", raw))
    if len(matches) > 1:
        return None, None, ["ambiguous_package_size"]
    if not matches:
        return None, None, []

    match = matches[0]
    value = float(match.group(1).replace(",", "."))
    raw_unit = match.group(2)
    multiplier, unit = {
        "l": (1000, "ml"),
        "ml": (1, "ml"),
        "kg": (1000, "g"),
        "g": (1, "g"),
        "gr": (1, "g"),
        "gab": (1, "piece"),
        "gb": (1, "piece"),
        "pcs": (1, "piece"),
        "pc": (1, "piece"),
        "pieces": (1, "piece"),
        "piece": (1, "piece"),
    }[raw_unit]
    if unit == "piece" and not value.is_integer():
        return None, None, ["invalid_package_size"]
    size = round(value * multiplier, 3)
    if unit == "piece" and re.search(
        r"(?:\b(?:komplekts|mānekļi|rotaļlietas)\b|\bmānekļ\.)", raw
    ):
        return None, None, ["ambiguous_package_size"]
    maximum = 20000 if unit in {"g", "ml"} else 1000
    if size <= 0:
        return None, None, ["invalid_package_size"]
    if size > maximum:
        return None, None, ["ambiguous_package_size"]
    return size, unit, []


def _provided_package(package_size, package_unit: str | None) -> tuple[float | None, str | None]:
    size = _as_float(package_size)
    unit = (package_unit or "").strip().lower()
    if size is None or size <= 0:
        return None, None
    if unit == "kg":
        return size * 1000, "g"
    if unit == "l":
        return size * 1000, "ml"
    if unit in {"g", "ml", "piece"}:
        return size, unit
    return None, None


def _prices_match(quantity: float, unit_price: float | None, line_total: float) -> bool:
    if quantity <= 0 or unit_price is None or line_total <= 0:
        return False
    return abs(quantity * unit_price - line_total) <= max(0.02, line_total * 0.02)


def _terminal_weight_unit(name: str | None) -> str | None:
    match = re.search(r"\b(kg|l)\s*$", (name or "").strip().lower())
    return match.group(1) if match else None


def calculate_normalized_unit_price(
    *,
    quantity: float,
    quantity_unit: str,
    line_total: float,
    package_size: float | None,
    package_unit: str | None,
) -> tuple[float | None, str]:
    if quantity <= 0 or line_total <= 0:
        return None, "unknown"

    if quantity_unit == "kg":
        return round(line_total / quantity, 4), "eur_per_kg"
    if quantity_unit == "g":
        return round(line_total / (quantity / 1000), 4), "eur_per_kg"
    if quantity_unit == "l":
        return round(line_total / quantity, 4), "eur_per_l"
    if quantity_unit == "ml":
        return round(line_total / (quantity / 1000), 4), "eur_per_l"

    if quantity_unit == "piece":
        if package_size and package_unit == "ml":
            return round(line_total / (quantity * package_size / 1000), 4), "eur_per_l"
        if package_size and package_unit == "g":
            return round(line_total / (quantity * package_size / 1000), 4), "eur_per_kg"
        if package_size and package_unit == "piece":
            return round(line_total / (quantity * package_size), 4), "eur_per_piece"
        return round(line_total / quantity, 4), "eur_per_piece"

    return None, "unknown"


def validate_price_data(data: ParsedPriceData) -> list[str]:
    warnings = list(data.warnings)
    if data.quantity <= 0:
        warnings.append("quantity_not_positive")
    if data.line_total < 0:
        warnings.append("line_total_negative")
    if data.unit_price is not None and data.unit_price < 0:
        warnings.append("unit_price_negative")
    if data.normalized_unit_price is not None:
        if data.normalized_unit_price <= 0:
            warnings.append("normalized_unit_price_not_positive")
        if data.normalized_unit_price > MAX_REASONABLE_NORMALIZED_PRICE:
            warnings.append("normalized_unit_price_suspicious")
    if data.package_size is not None and data.package_size <= 0:
        warnings.append("package_size_not_positive")
    if data.quantity_unit not in QUANTITY_UNITS:
        warnings.append("unknown_quantity_unit")
    if (data.package_unit or "unknown") not in PACKAGE_UNITS:
        warnings.append("unknown_package_unit")
    if data.normalized_price_unit not in NORMALIZED_UNITS:
        warnings.append("unknown_normalized_price_unit")
    if data.quantity_unit == "unknown":
        warnings.append("unknown_quantity_unit")
    if data.unit_price and data.quantity > 0:
        expected = data.quantity * data.unit_price
        if abs(expected - data.line_total) > max(0.02, data.line_total * 0.02):
            warnings.append("line_total_unit_price_mismatch")
    return sorted(set(warnings))


def derive_price_data(
    *,
    name: str,
    normalized_name: str | None = None,
    quantity=None,
    line_total=None,
    unit_price=None,
    quantity_unit: str | None = None,
    package_size=None,
    package_unit: str | None = None,
    source: str = "derived",
) -> ParsedPriceData:
    parsed_qty = _as_float(quantity)
    parsed_total = _as_float(line_total)
    qty = 1 if parsed_qty is None else parsed_qty
    total = 0 if parsed_total is None else parsed_total
    unit = normalize_quantity_unit(quantity_unit)
    parsed_unit_price = _as_float(unit_price)
    provided_unit_price = parsed_unit_price
    if parsed_unit_price is None and parsed_total is not None and qty > 0 and total >= 0:
        parsed_unit_price = round(total / qty, 4)

    warnings = []
    service_line = is_service_line(name)
    if service_line:
        warnings.append("service_line")
    if re.search(r"(?i)\b(?:čeks|ceks|receipt|rēķins)\b", name or ""):
        warnings.append("parser_contamination")

    supplied_size, supplied_unit = _provided_package(package_size, package_unit)
    inferred_size, inferred_unit, package_warnings = extract_package_size(name, normalized_name)
    warnings.extend(package_warnings)
    final_package_size = supplied_size if supplied_size is not None else inferred_size
    final_package_unit = supplied_unit if supplied_unit is not None else inferred_unit

    fatal_name = any(warning in {"parser_contamination", "multipack_unresolved"} for warning in warnings)
    fatal_package = any(warning in {"ambiguous_package_size", "invalid_package_size"} for warning in warnings)
    physical_unit = unit in {"kg", "g", "l", "ml"}
    if service_line:
        unit = "unknown"
        final_package_size = None
        final_package_unit = None
        normalized_unit_price, normalized_price_unit = None, "unknown"
        confidence = None
        result_source = "service_line"
    elif fatal_name or (fatal_package and supplied_size is None and not physical_unit):
        final_package_size = None
        final_package_unit = None
        normalized_unit_price, normalized_price_unit = None, "unknown"
        confidence = None
        result_source = "rejected"
    else:
        if unit != "unknown":
            confidence = {
                "parser": 0.95,
                "weighted_inference": 0.75,
                "package_name": 0.85,
                "inferred_piece": 0.70,
            }.get(source, 0.85 if final_package_size else 0.70)
            result_source = "parser" if source == "parser" else source
        elif (
            qty > 0
            and not float(qty).is_integer()
            and _terminal_weight_unit(name)
            and _prices_match(qty, provided_unit_price, total)
        ):
            unit = _terminal_weight_unit(name) or "unknown"
            confidence = 0.75
            result_source = "weighted_inference"
        elif qty > 0 and float(qty).is_integer() and final_package_size and parsed_total is not None and total > 0:
            unit = "piece"
            confidence = 0.85
            result_source = "package_name"
            warnings.append("quantity_unit_inferred_piece")
        elif qty > 0 and float(qty).is_integer() and parsed_total is not None and total > 0:
            unit = "piece"
            confidence = 0.70
            result_source = "inferred_piece"
            warnings.append("quantity_unit_inferred_piece")
        else:
            confidence = None
            result_source = "unresolved"

        normalized_unit_price, normalized_price_unit = calculate_normalized_unit_price(
            quantity=qty,
            quantity_unit=unit,
            line_total=total,
            package_size=final_package_size,
            package_unit=final_package_unit,
        )

    data = ParsedPriceData(
        quantity=qty,
        quantity_unit=unit,
        line_total=total,
        unit_price=parsed_unit_price,
        package_size=final_package_size,
        package_unit=final_package_unit or "unknown",
        normalized_unit_price=normalized_unit_price,
        normalized_price_unit=normalized_price_unit,
        source=result_source,
        confidence=confidence,
        warnings=warnings,
    )
    data.warnings = validate_price_data(data)
    return data


def are_price_units_comparable(item_a: dict, item_b: dict) -> bool:
    unit_a = item_a.get("normalized_price_unit") or "unknown"
    unit_b = item_b.get("normalized_price_unit") or "unknown"
    if unit_a == "unknown" or unit_b == "unknown" or unit_a != unit_b:
        return False
    if unit_a in {"eur_per_l", "eur_per_kg"}:
        return True
    if unit_a == "eur_per_piece":
        return (item_a.get("product_key") and item_a.get("product_key") == item_b.get("product_key")) or (
            item_a.get("canonical_name") and item_a.get("canonical_name") == item_b.get("canonical_name")
        )
    return False
