import argparse
import json
from pathlib import Path

from app import config, db


DEFAULT_SOURCE = config.BASE_DIR / "sample_data" / "receipts.json"


def _load_receipts(source: Path) -> list[dict]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("synthetic") is not True:
        raise ValueError("Sample data must be an object marked synthetic: true")
    receipts = payload.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("Sample data must contain a non-empty receipts list")

    receipt_numbers = set()
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("Each receipt must be an object")
        for field in ("date", "store", "receipt_number"):
            if not isinstance(receipt.get(field), str) or not receipt[field].strip():
                raise ValueError(f"Receipt {field} must be a non-empty string")
        if receipt["receipt_number"] in receipt_numbers:
            raise ValueError("Receipt numbers must be unique")
        receipt_numbers.add(receipt["receipt_number"])
        if not isinstance(receipt.get("total"), (int, float)) or isinstance(receipt["total"], bool):
            raise ValueError("Receipt total must be a number")
        items = receipt.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("Each receipt must contain a non-empty items list")
        if any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in items):
            raise ValueError("Each item must be an object with a name")
    return receipts


def create_sample_database(source: Path, target: Path, overwrite: bool = False) -> dict[str, int]:
    source = Path(source)
    target = Path(target).expanduser()
    receipts = _load_receipts(source)
    if target.resolve() == (config.DATA_DIR / "receipts.db").resolve():
        raise ValueError("Refusing to create sample data at the production database path")
    if target.exists() and not overwrite:
        raise FileExistsError(f"Target already exists: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    original_db_path = db.DB_PATH
    try:
        db.DB_PATH = target
        db.create_tables()
        for receipt in receipts:
            if not db.add_receipt_with_items(
                receipt["date"],
                receipt["store"],
                receipt["total"],
                receipt["receipt_number"],
                receipt["items"],
            ):
                raise ValueError(f"Duplicate receipt number: {receipt['receipt_number']}")
    finally:
        db.DB_PATH = original_db_path

    return {"receipts": len(receipts), "items": sum(len(receipt["items"]) for receipt in receipts)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a synthetic Receipt Tracker sample database")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    counts = create_sample_database(args.source, args.output, args.overwrite)
    print(f"Created {counts['receipts']} receipts and {counts['items']} items at {args.output}")


if __name__ == "__main__":
    main()
