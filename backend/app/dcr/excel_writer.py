"""Write DCR rows into the SOP 5-A1 tracker workbook without disturbing anything else in it.

openpyxl would drop the logo, the drop-down lists (x14 data validations), threaded comments and the
SharePoint metadata when saving. So instead we patch the "Main Sheet" XML inside the .xlsx directly:
only the touched <row> elements, the sheet dimension, the autofilter range and the drop-down ranges
change; every other part of the file is copied byte for byte. The pivot cache is flagged to refresh
on open so the "Occurence" sheet picks up new rows.
"""

import os
import re
import shutil
import tempfile
import time
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape, unescape

from app.dcr.normalize import parse_iso
from app.dcr.tracker_import import COLUMNS, SHEET

LETTERS = [chr(ord("A") + i) for i in range(len(COLUMNS))]  # A..U
DATE_COLUMNS = {"occurred_on", "closure_date"}
EXCEL_EPOCH = date(1899, 12, 30)
MAX_ROW_HEIGHT = 409
LOCK_RETRIES = 6


class WorkbookLockedError(RuntimeError):
    """The workbook is open in Excel (or otherwise locked) and cannot be replaced."""


def _sheet_part(z: zipfile.ZipFile) -> str:
    """Resolve the zip path of the "Main Sheet" worksheet via workbook.xml + its rels."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    m = re.search(r'<sheet [^>]*name="%s"[^>]*r:id="(rId\d+)"' % re.escape(SHEET), wb)
    if not m:
        raise ValueError(f"Sheet '{SHEET}' not found in workbook")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    t = re.search(r'<Relationship [^>]*Id="%s"[^>]*Target="([^"]+)"' % m.group(1), rels) or re.search(
        r'<Relationship [^>]*Target="([^"]+)"[^>]*Id="%s"' % m.group(1), rels
    )
    target = t.group(1).lstrip("/")
    return target if target.startswith("xl/") else "xl/" + target


def _row_xml(sheet: str, r: int) -> re.Match | None:
    return re.search(r'<row r="%d"[ >].*?</row>|<row r="%d"[^>]*/>' % (r, r), sheet, re.S)


def _cell_styles(row_xml: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r'<c r="([A-Z]+)\d+" s="(\d+)"', row_xml)}


def _last_filled_row(sheet: str) -> tuple[int, str]:
    """Last row whose column B (Type) has a value — its styles are the template for new rows."""
    best = None
    for m in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', sheet, re.S):
        if re.search(r'<c r="B%s"[^>]*t="(s|inlineStr|str)"[^>]*>' % m.group(1), m.group(0)):
            best = (int(m.group(1)), m.group(0))
    if not best:
        raise ValueError("No filled DCR rows found to copy styles from")
    return best


def _cell(ref: str, style: str | None, value) -> str:
    s = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{ref}"{s}/>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{s}><v>{value}</v></c>'
    text = escape(str(value)).replace("\r\n", "\n")
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _excel_value(field: str, value):
    if value is None:
        return None
    if field in DATE_COLUMNS:
        d = parse_iso(value)
        return (d - EXCEL_EPOCH).days if d else value
    if field == "project" and re.fullmatch(r"\d{1,12}", str(value)):
        return int(value)
    if field == "financial_impact" and re.fullmatch(r"\d+(\.\d+)?", str(value)):
        return float(value) if "." in str(value) else int(value)
    return value


def _row_height(values: dict[str, object]) -> float:
    # rough wrap estimate for the long text columns (col widths ~ 45-60 chars)
    lines = 1
    for field in ("description", "root_cause", "actions_taken", "capa_plan", "actions"):
        text = str(values.get(field) or "")
        est = sum(max(1, -(-len(part) // 55)) for part in text.split("\n")) if text else 1
        lines = max(lines, est)
    return min(MAX_ROW_HEIGHT, max(15.0, 15.0 * lines))


def _build_row(r: int, record: dict, styles: dict[str, str], keep_a: str | None) -> str:
    cells = []
    for letter, field in zip(LETTERS, COLUMNS):
        ref = f"{letter}{r}"
        if letter == "A" and keep_a:
            cells.append(keep_a)
            continue
        cells.append(_cell(ref, styles.get(letter), _excel_value(field, record.get(field))))
    ht = _row_height(record)
    return f'<row r="{r}" spans="1:21" ht="{ht:.2f}" customHeight="1">{"".join(cells)}</row>'


def _extend_ranges(sheet: str, last_row: int) -> str:
    # dimension, autofilter
    sheet = re.sub(
        r'<dimension ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"/>',
        lambda m: f'<dimension ref="{m.group(1)}{m.group(2)}:{m.group(3)}{max(int(m.group(4)), last_row)}"/>',
        sheet,
        count=1,
    )
    sheet = re.sub(
        r'<autoFilter ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"',
        lambda m: f'<autoFilter ref="{m.group(1)}{m.group(2)}:{m.group(3)}{max(int(m.group(4)), last_row)}"',
        sheet,
        count=1,
    )

    # drop-down lists: make sure every list column also covers the new rows
    def fix_sqref(m: re.Match) -> str:
        refs = m.group(1).split()
        cols = {re.match(r"[A-Z]+", ref).group(0) for ref in refs}
        extra = [f"{col}{last_row}" for col in sorted(cols) if not any(_covers(ref, col, last_row) for ref in refs)]
        return f"<xm:sqref>{' '.join(refs + extra)}</xm:sqref>"

    return re.sub(r"<xm:sqref>([^<]+)</xm:sqref>", fix_sqref, sheet)


def _covers(ref: str, col: str, row: int) -> bool:
    m = re.fullmatch(r"([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?", ref)
    if not m or m.group(1) != col:
        return False
    return int(m.group(2)) <= row <= int(m.group(4) or m.group(2))


def _patch_workbook_xml(xml: str, last_row: int) -> str:
    return re.sub(
        r"(_xlnm\._FilterDatabase\"[^>]*>'?Main Sheet'?!\$[A-Z]+\$\d+:\$[A-Z]+\$)(\d+)",
        lambda m: m.group(1) + str(max(int(m.group(2)), last_row)),
        xml,
    )


def _patch_pivot_cache(xml: str) -> str:
    if "refreshOnLoad=" in xml:
        return xml
    return xml.replace("<pivotCacheDefinition ", '<pivotCacheDefinition refreshOnLoad="1" ', 1)


def write_rows(path: Path, rows: list[tuple[int | None, dict]]) -> list[int]:
    """Write records into the workbook.

    `rows` is a list of (row_number or None, record dict keyed by tracker field names).
    row_number None = new entry: it fills the pre-numbered empty row carrying the same tracking number
    if there is one, otherwise it is appended after the last used row. Returns the row numbers written.
    """
    with zipfile.ZipFile(path) as z:
        part = _sheet_part(z)
        sheet = z.read(part).decode("utf-8")
        workbook_xml = z.read("xl/workbook.xml").decode("utf-8")
        strings = _shared_strings(z)
        pivots = {n: z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("xl/pivotCache/pivotCacheDefinition")}

    _, template_row = _last_filled_row(sheet)
    styles = _cell_styles(template_row)
    # both date columns use the "DCR occurred on" date format (dd/mm/yyyy)
    for letter, field in zip(LETTERS, COLUMNS):
        if field in DATE_COLUMNS and "D" in styles:
            styles[letter] = styles["D"]
    written: list[int] = []

    for row_number, record in rows:
        tracking = record.get("tracking_number")
        if row_number is None:
            row_number = _find_prenumbered(sheet, tracking, strings) or _next_free_row(sheet)
        existing = _row_xml(sheet, row_number)
        if existing:
            keep_a = None
            a = re.search(r'<c r="A%d"[^>]*?(?:/>|>.*?</c>)' % row_number, existing.group(0), re.S)
            if a and tracking and _a_text(existing.group(0), strings) == tracking:
                keep_a = a.group(0)  # keep the original cell (shared string + style)
            sheet = sheet[: existing.start()] + _build_row(row_number, record, styles, keep_a) + sheet[existing.end():]
        else:
            sheet = _insert_row(sheet, row_number, _build_row(row_number, record, styles, None))
        written.append(row_number)

    last = max(written + [_max_row(sheet)])
    sheet = _extend_ranges(sheet, last)
    workbook_xml = _patch_workbook_xml(workbook_xml, last)
    pivots = {n: _patch_pivot_cache(x) for n, x in pivots.items()}
    _replace_parts(path, {part: sheet, "xl/workbook.xml": workbook_xml, **pivots})
    return written


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    raw = z.read("xl/sharedStrings.xml").decode("utf-8")
    return [unescape(re.sub(r"<[^>]+>", "", si)).strip() for si in re.findall(r"<si>(.*?)</si>", raw, re.S)]


def _a_text(row_xml: str, strings: list[str]) -> str | None:
    m = re.search(r'<c r="A\d+"[^>]*t="inlineStr"[^>]*><is><t[^>]*>([^<]*)</t>', row_xml)
    if m:
        return unescape(m.group(1)).strip()
    m = re.search(r'<c r="A\d+"[^>]*t="s"[^>]*><v>(\d+)</v>', row_xml)
    if m and int(m.group(1)) < len(strings):
        return strings[int(m.group(1))]
    return None


def _find_prenumbered(sheet: str, tracking: str | None, strings: list[str]) -> int | None:
    """A row that has only column A filled with this tracking number (the tracker pre-numbers cases)."""
    if not tracking:
        return None
    for m in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', sheet, re.S):
        if re.search(r'<c r="[B-U]\d+"[^>]*>\s*<(v|is)>', m.group(2)):
            continue
        if _a_text(m.group(0), strings) == tracking:
            return int(m.group(1))
    return None


def _max_row(sheet: str) -> int:
    rows = [int(x) for x in re.findall(r'<row r="(\d+)"', sheet)]
    return max(rows) if rows else 1


def _next_free_row(sheet: str) -> int:
    """First row after the last row that has anything in columns A..U."""
    last = 1
    for m in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', sheet, re.S):
        if re.search(r'<c r="[A-U]\d+"[^>]*>\s*<(v|is)>', m.group(2)):
            last = int(m.group(1))
    return last + 1


def _insert_row(sheet: str, r: int, row_xml: str) -> str:
    for m in re.finditer(r'<row r="(\d+)"', sheet):
        if int(m.group(1)) > r:
            return sheet[: m.start()] + row_xml + sheet[m.start():]
    i = sheet.index("</sheetData>")
    return sheet[:i] + row_xml + sheet[i:]


def _replace_parts(path: Path, parts: dict[str, str]) -> None:
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=str(path.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data = parts[item.filename].encode("utf-8") if item.filename in parts else src.read(item.filename)
                dst.writestr(item, data)
        # OneDrive/antivirus hold new files briefly; Excel holds them until closed
        for attempt in range(LOCK_RETRIES):
            try:
                os.replace(tmp, path)
                break
            except PermissionError as e:
                if attempt == LOCK_RETRIES - 1:
                    raise WorkbookLockedError(f"'{path.name}' is locked — close it in Excel and try again.") from e
                time.sleep(0.5)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def ensure_working_copy(template: Path, target: Path) -> Path:
    """Create the working tracker from the template on first use."""
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, target)
    return target
