"""Clean-up helpers shared by the tracker import and the e-mail extractor."""

import re
from datetime import date, datetime

from app.dcr.schema import CATEGORIES, DCR_TYPES, OFFICES, RESPONSIBLE_PARTIES

EMPTY_MARKERS = {"", "-", "--", "none", "tbd", "?"}
NA_MARKERS = {"n/a", "na", "n.a.", "not applicable"}


def clean_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.lower() in EMPTY_MARKERS:
        return None
    if text.lower() in NA_MARKERS:
        return "N/A"
    return text


def is_blank(value: str | None) -> bool:
    return value is None or value == "N/A"


def to_iso_date(value) -> str | None:
    """Accepts datetime/date objects and the text formats seen in the tracker."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _match(value: str | None, options: list[str]) -> str | None:
    """Case/whitespace-insensitive match against a drop-down list; returns the raw text if no match."""
    if value is None:
        return None
    key = re.sub(r"\s+", " ", value).strip().lower()
    for option in options:
        if option.lower() == key:
            return option
    # tolerate simple plurals, e.g. "missing items"
    for option in options:
        if key.rstrip("s") == option.lower():
            return option
    return value.strip()


def norm_type(value) -> str | None:
    return _match(clean_text(value), DCR_TYPES)


def norm_category(value) -> str | None:
    return _match(clean_text(value), CATEGORIES)


def norm_responsible(value) -> str | None:
    return _match(clean_text(value), RESPONSIBLE_PARTIES)


def norm_office(value) -> str | None:
    return _match(clean_text(value), OFFICES)


def norm_yn(value) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    upper = text.upper()
    if upper in {"Y", "YES"} or upper.startswith("CAPA NEEDED"):
        return "Y"
    if upper in {"N", "NO"}:
        return "N"
    return text


def parse_financial(value: str | None) -> tuple[float, str | None]:
    """Best-effort amount + currency from the free-text "Financial impact" column.

    Plain numbers are EUR (the tracker's default); "$"/"USD" marks US dollars; text without a
    number (e.g. "None", "To be determined") is 0.
    """
    if not value or value == "N/A":
        return 0.0, None
    text = str(value).strip()
    currency = "USD" if re.search(r"\$|usd", text, re.I) else "EUR"
    m = re.search(r"\d[\d.,\s]*", text)
    if not m:
        return 0.0, None
    num = m.group(0).strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", num):  # 1.785 / 8.177,00
        num = num.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", num):  # 8,177.00
        num = num.replace(",", "")
    else:
        num = num.replace(",", ".")
    try:
        return float(num.rstrip(".")), currency
    except ValueError:
        return 0.0, None
