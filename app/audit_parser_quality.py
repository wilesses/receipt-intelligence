import argparse
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from app.db import DB_PATH
from app.price_model import extract_package_size, is_service_line
from app.receipt_parser import (
    GLUED_PACKAGE_PATTERN,
    PACKAGE_UNIT_PATTERN,
    is_receipt_metadata_line,
    parser_quality_issue,
    preprocess_receipt_text,
)


DECIMAL_CORRUPTION = re.compile(rf"\b\d+,\s+\d+\s*{PACKAGE_UNIT_PATTERN}\b", re.IGNORECASE)
LKG = re.compile(r"(?<!\w)lkg\b", re.IGNORECASE)
M1 = re.compile(r"\b\d+(?:[.,]\d+)?\s*m1\b", re.IGNORECASE)
RECEIPT_HEADER = re.compile(r"^(?:čeks|ceks)(?:\s|$)", re.IGNORECASE)
MULTIPACK = re.compile(
    rf"\b\d+\s*[xх×]\s*\d+(?:[.,]\d+)?\s*{PACKAGE_UNIT_PATTERN}\b|\b\d+\s*\+\s*\d+\b",
    re.IGNORECASE,
)

GROUP_DETAILS = {
    "ocr_decimal_corruption": ("OCR/text extraction", "whitespace split inside decimal package value"),
    "ocr_lkg": ("OCR", "ambiguous l/1 substitution before kg"),
    "ocr_m1": ("OCR", "ambiguous l/1 substitution in ml"),
    "receipt_header": ("parser name boundary", "receipt header leaked into product name"),
    "cashier_line": ("parser sanitation", "cashier or terminal metadata treated as product text"),
    "service_line": ("parser sanitation", "known non-product fee or bag line"),
    "multipack": ("post-processing", "valid multipack needs separate quantity semantics"),
    "glued_tokens": ("OCR/tokenizer", "product text and package token have no reliable boundary"),
    "ambiguous_package_size": ("regex/post-processing", "multiple or ambiguous package interpretations"),
    "unknown": ("unknown", "no narrow contamination signature; includes normal products"),
}


def classify_name(name: str) -> str:
    text = " ".join((name or "").strip().split())
    if DECIMAL_CORRUPTION.search(text):
        return "ocr_decimal_corruption"
    if LKG.search(text):
        return "ocr_lkg"
    if M1.search(text):
        return "ocr_m1"
    if RECEIPT_HEADER.search(text):
        return "receipt_header"
    if is_receipt_metadata_line(text):
        return "cashier_line"
    if is_service_line(text):
        return "service_line"
    if MULTIPACK.search(text):
        return "multipack"
    if GLUED_PACKAGE_PATTERN.search(text):
        return "glued_tokens"
    _, _, warnings = extract_package_size(text)
    if {"ambiguous_package_size", "invalid_package_size"}.intersection(warnings):
        return "ambiguous_package_size"
    return "unknown"


def projected_action(name: str, group: str) -> str:
    preprocessed = preprocess_receipt_text(name)
    if is_receipt_metadata_line(preprocessed) or parser_quality_issue(preprocessed):
        return "rejected"
    final_group = classify_name(preprocessed)
    if final_group in {"multipack", "ambiguous_package_size"}:
        return "unresolved"
    if preprocessed != name:
        return "corrected"
    return "unchanged"


def audit_database(path: str | Path, example_limit: int = 5) -> dict:
    db_path = Path(path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    uri = db_path.as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        rows = conn.execute("SELECT id, name FROM items ORDER BY id").fetchall()

    counts = Counter()
    actions = Counter()
    examples = defaultdict(list)
    for row in rows:
        group = classify_name(row["name"] or "")
        action = projected_action(row["name"] or "", group)
        counts[group] += 1
        actions[action] += 1
        if len(examples[group]) < example_limit:
            examples[group].append({"id": row["id"], "name": row["name"], "action": action})

    return {
        "database": str(db_path),
        "rows": len(rows),
        "counts": dict(counts),
        "actions": dict(actions),
        "examples": dict(examples),
    }


def print_report(result: dict) -> None:
    print(f"Database: {result['database']}")
    print(f"Rows checked: {result['rows']}")
    for group in GROUP_DETAILS:
        count = result["counts"].get(group, 0)
        layer, cause = GROUP_DETAILS[group]
        print(f"{group}: {count} | layer={layer} | cause={cause}")
        for example in result["examples"].get(group, []):
            print(f"  #{example['id']}: {example['name']} | action={example['action']}")
    for action in ("corrected", "rejected", "unresolved", "unchanged"):
        print(f"projected {action}: {result['actions'].get(action, 0)}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Read-only audit of parser-quality issues in stored item names.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--examples", type=int, default=5)
    args = parser.parse_args()
    print_report(audit_database(args.db, max(0, args.examples)))


if __name__ == "__main__":
    main()
