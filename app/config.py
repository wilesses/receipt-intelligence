import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PDF_IMPORT_DIR = DATA_DIR / "pdf_receipts"
DB_PATH = Path(os.getenv("RECEIPT_DB_PATH", DATA_DIR / "receipts.db")).expanduser()


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PDF_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
