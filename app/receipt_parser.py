import re
from app.category_keywords import CATEGORY_KEYWORDS


def parse_money(value: str) -> float:
    return float(value.replace(",", "."))


def categorize_item(name: str) -> str:
    name_lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in name_lower:
                return category
    return "прочее"


def parse_rimi_receipt(lines: list[str]) -> dict:
    result = {"store": "RIMI", "date": None, "total": None, "items": []}

    normalized_lines = [line.replace("—", "-").replace("–", "-") for line in lines]

    for line in normalized_lines:
        if "laiks" in line.lower():
            if match := re.search(r"(\d{4})[-.](\d{2})[-.](\d{2})", line):
                result["date"] = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                break

    if result["date"] is None:
        for line in normalized_lines:
            if match := re.search(r"(\d{4})[-.](\d{2})[-.](\d{2})|(\d{2})\.(\d{2})\.(\d{4})", line):
                value = match.group(0)
                if "." in value:
                    day, month, year = value.split(".")
                    result["date"] = f"{year}-{month}-{day}"
                else:
                    result["date"] = value
                break

    for line in reversed(normalized_lines):
        if "kopa" in line.lower() or "kopā" in line.lower():
            if match := re.search(r"(\d+,\d{2})", line):
                result["total"] = parse_money(match.group(1))
                break

    qty_line_pattern = re.compile(
        r"(?P<qty>\d+(?:,\d+)?)\s*(?:gab|kg)\s+X\s+"
        r"(?P<unit_price>\d+,\d{2})\s*EUR(?:/kg)?"
        r"(?:\s+(?P<line_total>\d+,\d{2}))?",
        re.IGNORECASE,
    )
    stop_words = [
        "sia rimi", "jur. adrese", "kase nr", "pvn", "sasijas", "čeks", "ceks",
        "elektroniska", "klients", "atlaides", "tavs letaupijums", "maksajumu",
        "apmaksa", "bankas", "terminala", "tirgotaja", "laiks", "visa", "kopa",
        "kopā", "saglabajiet", "rrn", "nopelnita",
    ]
    ignore_name_words = ["atl.", "gala cena"]

    for index, line in enumerate(normalized_lines):
        match = qty_line_pattern.search(line)
        if not match:
            continue

        name_parts = []
        cursor = index - 1
        while cursor >= 0 and len(name_parts) < 3:
            previous = normalized_lines[cursor].strip()
            previous_lower = previous.lower()
            if (
                not previous
                or qty_line_pattern.search(previous)
                or any(word in previous_lower for word in stop_words)
                or any(word in previous_lower for word in ignore_name_words)
            ):
                break
            name_parts.insert(0, previous)
            cursor -= 1

        name = " ".join(name_parts).strip()
        if not name:
            continue

        quantity = parse_money(match.group("qty"))
        unit_price = parse_money(match.group("unit_price"))
        line_total = match.group("line_total")
        price = parse_money(line_total) if line_total else round(quantity * unit_price, 2)
        for lookahead in normalized_lines[index + 1:index + 4]:
            lookahead_lower = lookahead.lower()
            if qty_line_pattern.search(lookahead):
                break
            if not (lookahead_lower.startswith("atl") or "gala cena" in lookahead_lower):
                break
            if "gala cena" in lookahead_lower:
                if discount_match := re.search(r"(\d+,\d{2})\s*$", lookahead):
                    price = parse_money(discount_match.group(1))
                    break

        result["items"].append({
            "name": name,
            "quantity": quantity,
            "price": price,
            "category": categorize_item(name),
        })

    return result


def parse_receipt(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    if any("rimi" in line.lower() for line in lines):
        rimi_result = parse_rimi_receipt(lines)
        if rimi_result["items"]:
            return rimi_result

    result = {"store": "MAXIMA", "date": None, "total": None, "items": []}

    # 1. Дата
    for line in lines:
        if match := re.search(r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}", line):
            result["date"] = match.group(0)
            break

    # 2. Итоговая сумма
    for line in reversed(lines):
        if "kopā apmaksai" in line.lower():
            if match := re.search(r"\d+,\d{2}", line):
                result["total"] = float(match.group(0).replace(",", "."))
                break

    items = []
    skip_words = ["atlaide", "kopā", "summa", "apmaksai"]
    i = 0
    last_item = None

    while i < len(lines):
        line = lines[i]

        # Строка с товаром
        if re.search(r"\d+,\d{2}\s+X\s+[\d,]+", line):
            # Название = предыдущие строки (пока не пустая или не служебная)
            name_parts = []
            j = i - 1
            while j >= 0:
                prev = lines[j].strip()
                if not prev or any(w in prev.lower() for w in skip_words):
                    break
                # Стоп, если строка похожа на цену
                if re.search(r"\d+,\d{2}\s+X\s+", prev):
                    break
                name_parts.insert(0, prev)
                # Если собрали 2 строки или название длинное → стоп
                if len(name_parts) >= 2 or len(prev) > 20:
                    break
                j -= 1

            name = " ".join(name_parts).strip()

            # Количество
            qty_match = re.search(r"X\s+([\d,]+)", line)
            quantity = float(qty_match.group(1).replace(",", ".")) if qty_match else 1.0

            # Цена (берем скидочную)
            price = None
            for k in range(1, 3):
                if i + k < len(lines) and "cena ar atlaidi" in lines[i + k].lower():
                    if m := re.search(r"(\d+,\d{2})", lines[i + k]):
                        price = float(m.group(1).replace(",", "."))
                        break
            if price is None:  # fallback
                if m := re.search(r"(\d+,\d{2})\s+[A-Z]?$", line):
                    price = float(m.group(1).replace(",", "."))

            # Категория
            category = categorize_item(name)

            # Добавляем
            last_item = {
                "name": name,
                "price": price,
                "quantity": quantity,
                "category": category
            }
            items.append(last_item)

        i += 1

    result["items"] = items
    return result
