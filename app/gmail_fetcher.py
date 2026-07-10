import datetime
import email
import imaplib
import os
from dataclasses import dataclass
from email.header import decode_header
from email.message import Message
from email.utils import parseaddr
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from app.config import PDF_IMPORT_DIR, ensure_data_dirs


load_dotenv()


@dataclass
class GmailFetchResult:
    emails_checked: int
    emails_matched: int
    files_saved: list[Path]
    files_existing: list[Path]
    skipped_files: list[str]


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).split("#", 1)[0].strip()
    return int(value or default)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.split("#", 1)[0].strip().lower() in {"1", "true", "yes", "on"}


def gmail_settings() -> dict:
    app_password = os.getenv("APP_PASSWORD")
    if app_password:
        app_password = "".join(app_password.split())

    senders = [
        sender.strip().lower()
        for sender in os.getenv("GMAIL_SENDERS", "").split(",")
        if sender.strip()
    ]
    return {
        "imap_server": os.getenv("IMAP_SERVER"),
        "email_account": os.getenv("EMAIL_ACCOUNT"),
        "app_password": app_password,
        "save_folder": Path(os.getenv("SAVE_FOLDER", str(PDF_IMPORT_DIR))),
        "days_lookback": _env_int("DAYS_LOOKBACK", 7),
        "max_emails": _env_int("GMAIL_MAX_EMAILS", 300),
        "import_existing": _env_bool("GMAIL_IMPORT_EXISTING", False),
        "raw_query": os.getenv("GMAIL_RAW_QUERY", "").strip(),
        "senders": senders,
    }


def decode_mime_value(raw_value: str | None) -> str:
    if not raw_value:
        return ""

    decoded_parts = decode_header(raw_value)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            candidate_encodings = []
            if encoding and encoding.lower() != "unknown-8bit":
                candidate_encodings.append(encoding)
            candidate_encodings.extend(["utf-8", "cp1257", "latin1"])

            for candidate in candidate_encodings:
                try:
                    result += part.decode(candidate, errors="ignore")
                    break
                except LookupError:
                    continue
        else:
            result += part
    return result


def connect_to_gmail():
    settings = gmail_settings()
    missing = [
        key
        for key in ("imap_server", "email_account", "app_password")
        if not settings[key]
    ]
    if missing:
        raise RuntimeError("Не заполнены настройки Gmail в .env")

    mail = imaplib.IMAP4_SSL(settings["imap_server"])
    try:
        mail.login(settings["email_account"], settings["app_password"])
    except imaplib.IMAP4.error as exc:
        raise RuntimeError(
            "Gmail отклонил логин. Проверь, что в .env указан пароль приложения Gmail, "
            "а не обычный пароль аккаунта. Для Gmail нужна включенная двухэтапная "
            "проверка и App Password для Mail."
        ) from exc
    return mail


def _message_sender(message: Message) -> str:
    return parseaddr(decode_mime_value(message.get("From")))[1].lower()


def _sender_allowed(message: Message, allowed_senders: list[str]) -> bool:
    if not allowed_senders:
        return True
    return _message_sender(message) in allowed_senders


def _unique_path(folder: Path, filename: str) -> Path:
    target = folder / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _search_email_ids(mail, settings: dict, since_date: str) -> list[bytes]:
    raw_query = settings["raw_query"]
    if raw_query:
        print(f"Gmail: поиск PDF-вложений: {raw_query}", flush=True)
        status, messages = mail.search(None, "X-GM-RAW", f'"{raw_query}"')
        if status == "OK":
            return messages[0].split()

    email_ids = []
    search_senders = settings["senders"] or [None]
    for sender in search_senders:
        if sender:
            query = f'(FROM "{sender}" SINCE {since_date})'
        else:
            query = f"(SINCE {since_date})"
        print(f"Gmail: запасной поиск писем {query}", flush=True)
        status, messages = mail.search(None, query)
        if status != "OK":
            raise RuntimeError("Gmail не вернул список писем")
        email_ids.extend(messages[0].split())

    return email_ids


def fetch_pdf_attachments(mail=None) -> GmailFetchResult:
    settings = gmail_settings()
    ensure_data_dirs()
    save_folder = settings["save_folder"]
    save_folder.mkdir(parents=True, exist_ok=True)

    owns_connection = mail is None
    if mail is None:
        print("Gmail: подключение...", flush=True)
        mail = connect_to_gmail()

    try:
        print("Gmail: открываю inbox...", flush=True)
        mail.select("inbox")
        since_date = (
            datetime.date.today() - datetime.timedelta(days=settings["days_lookback"])
        ).strftime("%d-%b-%Y")

        files_saved: list[Path] = []
        files_existing: list[Path] = []
        skipped_files: list[str] = []
        email_ids = _search_email_ids(mail, settings, since_date)

        email_ids = list(dict.fromkeys(email_ids))
        email_ids = email_ids[-settings["max_emails"]:]
        print(f"Gmail: найдено писем для проверки: {len(email_ids)}", flush=True)

        for index, num in enumerate(email_ids, 1):
            print(f"Gmail: письмо {index}/{len(email_ids)}", flush=True)
            _, data = mail.fetch(num, "(RFC822)")
            message = email.message_from_bytes(data[0][1])

            if not _sender_allowed(message, settings["senders"]):
                continue

            for part in message.walk():
                content_disposition = str(part.get("Content-Disposition") or "")
                if "attachment" not in content_disposition.lower():
                    continue

                filename = decode_mime_value(part.get_filename())
                if not filename or not filename.lower().endswith(".pdf"):
                    if filename:
                        skipped_files.append(filename)
                    continue

                safe_filename = secure_filename(filename)
                file_path = save_folder / safe_filename
                if file_path.exists():
                    files_existing.append(file_path)
                    print(f"Gmail: PDF уже есть {safe_filename}", flush=True)
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    skipped_files.append(filename)
                    continue

                file_path.write_bytes(payload)
                files_saved.append(file_path)
                print(f"Gmail: сохранен PDF {file_path.name}", flush=True)

        return GmailFetchResult(
            emails_checked=len(email_ids),
            emails_matched=len(email_ids),
            files_saved=files_saved,
            files_existing=files_existing,
            skipped_files=skipped_files,
        )
    finally:
        if owns_connection:
            mail.logout()


def main():
    result = fetch_pdf_attachments()
    print(f"Проверено писем: {result.emails_checked}")
    print(f"Сохранено PDF: {len(result.files_saved)}")
    for file_path in result.files_saved:
        print(file_path)


if __name__ == "__main__":
    main()
