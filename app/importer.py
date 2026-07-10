import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pdfplumber

from app.category_keywords import categorize_from_name
from app.config import PDF_IMPORT_DIR, ensure_data_dirs
from app.db import add_receipt_with_items, create_tables
from app.receipt_parser import parse_receipt


class PdfTextExtractionError(Exception):
    pass


def find_executable(name: str, candidates: list[str]) -> str | None:
    configured_path = os.getenv(f"{name.upper()}_CMD")
    if configured_path and Path(configured_path).exists():
        return configured_path

    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    path_value = shutil.which(name)
    if path_value:
        return path_value

    return None


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        if text_parts:
            return "\n".join(text_parts)

        has_images = any(page.images for page in pdf.pages)

    if has_images:
        return extract_text_with_ocr(pdf_path)

    raise PdfTextExtractionError("В PDF нет текстового слоя")


def extract_text_with_ocr(pdf_path: str | Path) -> str:
    pdftoppm_path = find_executable("pdftoppm", [
        r"C:\Users\bakla\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe",
    ])
    tesseract_path = find_executable("tesseract", [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ])

    if not pdftoppm_path or not tesseract_path:
        raise PdfTextExtractionError(
            "PDF выглядит как скан/картинка. Для таких чеков нужен OCR: установи Tesseract и добавь его в PATH."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        image_prefix = Path(tmpdir) / "page"
        subprocess.run(
            [pdftoppm_path, "-png", "-r", "220", str(pdf_path), str(image_prefix)],
            check=True,
            capture_output=True,
            text=True,
        )

        text_parts = []
        for image_path in sorted(Path(tmpdir).glob("page-*.png")):
            completed = subprocess.run(
                [tesseract_path, str(image_path), "stdout", "-l", "lav+eng"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            if completed.stdout.strip():
                text_parts.append(completed.stdout)

    text = "\n".join(text_parts).strip()
    if not text:
        raise PdfTextExtractionError("OCR не смог распознать текст в PDF")

    return text


def get_pdf_text_diagnostics(pdf_path: str | Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        chars_by_page = []
        images_by_page = []
        for page in pdf.pages:
            chars_by_page.append(len(page.extract_text() or ""))
            images_by_page.append(len(page.images))

    return {
        "pages": len(chars_by_page),
        "text_chars": sum(chars_by_page),
        "images": sum(images_by_page),
        "looks_scanned": sum(chars_by_page) == 0 and sum(images_by_page) > 0,
    }


def extraction_error_message(file_path: str | Path, exc: Exception) -> str:
    try:
        diagnostics = get_pdf_text_diagnostics(file_path)
    except Exception:
        diagnostics = None

    if diagnostics and diagnostics["looks_scanned"]:
        return (
            "Не удалось извлечь текст: PDF выглядит как скан/картинка. "
            "Обычный парсер читает только PDF с текстовым слоем. "
            "Для Rimi-чеков такого типа нужен OCR."
        )

    return f"Не удалось извлечь текст: {exc}"


def normalize_date(date: str | None) -> str | None:
    if date and "." in date:
        day, month, year = date.split(".")
        return f"{year}-{month}-{day}"
    return date


def prepare_receipt_data(file_path: str | Path) -> dict:
    try:
        text = extract_text_from_pdf(file_path)
    except PdfTextExtractionError as exc:
        return {"status": "error", "error": extraction_error_message(file_path, exc)}

    if not text.strip():
        return {"status": "error", "error": extraction_error_message(file_path, PdfTextExtractionError("пустой текст"))}

    data = parse_receipt(text)
    if not data.get("items"):
        return {"status": "error", "error": "Нет товаров в чеке"}

    for item in data["items"]:
        item["category"] = categorize_from_name(item.get("name", ""))
        item["price"] = item.get("price") or 0
        item["quantity"] = item.get("quantity") or 1

    total = data.get("total")
    if total is None or total == 0:
        total = sum(item["price"] for item in data["items"])

    return {
        "status": "ok",
        "date": normalize_date(data.get("date")),
        "store": data.get("store") or "Unknown",
        "total": round(total, 2),
        "items": data["items"],
    }


def process_pdf_api(file_path: str | Path) -> dict:
    try:
        data = prepare_receipt_data(file_path)
        if data["status"] != "ok":
            return data

        receipt_number = Path(file_path).stem
        success = add_receipt_with_items(
            date=data["date"],
            store=data["store"],
            total=data["total"],
            receipt_number=receipt_number,
            items=data["items"],
        )

        if not success:
            return {"status": "error", "error": "Чек уже существует"}

        return {"status": "ok", "message": f"Чек импортирован ({len(data['items'])} товаров)"}
    except Exception as exc:
        return {"status": "error", "error": f"Ошибка: {exc}"}


def process_pdf(file_path: str | Path) -> bool:
    result = process_pdf_api(file_path)
    if result["status"] == "ok":
        print(result["message"])
        return True

    print(result["error"])
    return False


def import_all_pdfs() -> None:
    ensure_data_dirs()
    create_tables()

    files = sorted(path for path in PDF_IMPORT_DIR.iterdir() if path.suffix.lower() == ".pdf")
    if not files:
        print("Нет новых PDF для импорта.")
        return

    for file_path in files:
        if process_pdf(file_path):
            os.remove(file_path)


if __name__ == "__main__":
    import_all_pdfs()
