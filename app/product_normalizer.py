import re


LATIN_LV = "a-zāčēģīķļņōŗšūž"
TECHNICAL_TOKENS = {"d", "pet", "sk"}


def _format_decimal(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _normalize_unit(match: re.Match) -> str:
    value = float(match.group("value"))
    unit = match.group("unit").lower().rstrip(".")

    if unit in {"l"}:
        return f"{round(value * 1000)}ml"
    if unit in {"ml"}:
        return f"{round(value)}ml"
    if unit in {"kg"}:
        return f"{round(value * 1000)}g"
    if unit in {"g", "gr"}:
        return f"{round(value)}g"
    return f"{_format_decimal(value)}gab"


def normalize_product_name(name: str | None) -> str:
    if not name:
        return ""

    text = str(name).lower()
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(rf"[^0-9{LATIN_LV}%.\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    text = re.sub(
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ml|l|kg|gr|g|gab)\.?\b",
        _normalize_unit,
        text,
    )
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1%", text)

    tokens = []
    for token in text.split():
        clean = token.strip(".")
        if clean in TECHNICAL_TOKENS:
            continue
        tokens.append(clean)

    return " ".join(tokens)


def extract_product_features(normalized_name: str) -> dict:
    text = normalized_name or ""
    volume = re.search(r"\b(\d+)ml\b", text)
    weight = re.search(r"\b(\d+)g\b", text)
    percentage = re.search(r"\b(\d+(?:\.\d+)?)%", text)

    return {
        "volume_ml": int(volume.group(1)) if volume else None,
        "weight_g": int(weight.group(1)) if weight else None,
        "percentage": float(percentage.group(1)) if percentage else None,
    }

