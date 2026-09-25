"""DCR tracker API: dashboard, records, e-mail ingestion and the Excel tracker download."""

from collections import Counter
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.dcr.email_parser import parse_any
from app.dcr.excel_writer import WorkbookLockedError
from app.dcr.extractor import CLAUDE_MODEL, use_claude
from app.dcr.normalize import parse_financial, parse_iso
from app.dcr.schema import CATEGORIES, DCR, DCR_TYPES, OFFICES, RESPONSIBLE_PARTIES, DCRUpdate
from app.dcr.store import TRACKER_PATH, store

router = APIRouter(prefix="/api", tags=["dcr"])


def _locked(e: WorkbookLockedError) -> HTTPException:
    return HTTPException(409, str(e))


def _confirmed() -> list[DCR]:
    return [r for r in store.all() if r.status != "Draft"]


def _sort_newest(records: list[DCR]) -> list[DCR]:
    return sorted(records, key=lambda r: (r.occurred_on or "", r.tracking_number or ""), reverse=True)


# ---------------------------------------------------------------- meta & dashboard


@router.get("/meta")
def meta() -> dict:
    confirmed = _confirmed()
    customers = sorted({r.customer for r in confirmed if r.customer and r.customer != "N/A"}, key=str.lower)
    return {
        "types": DCR_TYPES,
        "categories": CATEGORIES,
        "responsible_parties": RESPONSIBLE_PARTIES,
        "offices": OFFICES,
        "customers": customers,
        "record_count": len(confirmed),
        "draft_count": sum(r.status == "Draft" for r in store.all()),
        "next_tracking_number": store.next_tracking_number(),
        "tracker_file": TRACKER_PATH.name,
        "extractor": "claude" if use_claude() else "rules",
        "model": CLAUDE_MODEL if use_claude() else None,
        "today": date.today().isoformat(),
    }


@router.get("/dashboard")
def dashboard() -> dict:
    recs = _confirmed()
    open_recs = [r for r in recs if r.status == "Open"]
    this_year = str(date.today().year)

    ytd_eur = 0.0
    for r in recs:
        if (r.occurred_on or "").startswith(this_year):
            amount, currency = parse_financial(r.financial_impact)
            if currency == "EUR":
                ytd_eur += amount

    by_type = Counter(r.type for r in recs if r.type)
    by_category = Counter(r.category or "Not set" for r in recs)

    occurred = Counter(r.occurred_on[:4] for r in recs if parse_iso(r.occurred_on))
    closed = Counter(r.closure_date[:4] for r in recs if parse_iso(r.closure_date))
    years = sorted(y for y in set(occurred) | set(closed) if y >= "2023")

    attention = sorted((r for r in open_recs if r.critical == "Y"), key=lambda r: r.occurred_on or "")[:7]

    return {
        "year": int(this_year),
        "kpis": {
            "open": len(open_recs),
            "critical_open": sum(r.critical == "Y" for r in open_recs),
            "capa_pending": sum(r.capa_needed == "Y" for r in open_recs),
            "financial_ytd_eur": round(ytd_eur, 2),
            "total": len(recs),
            "drafts": sum(r.status == "Draft" for r in store.all()),
        },
        "by_type": [{"name": t, "count": by_type.get(t, 0)} for t in DCR_TYPES],
        "by_category": [{"name": k, "count": v} for k, v in by_category.most_common()],
        "trend": [{"year": y, "occurred": occurred.get(y, 0), "closed": closed.get(y, 0)} for y in years],
        "attention": attention,
    }


# ---------------------------------------------------------------- records


@router.get("/dcrs", response_model=list[DCR])
def list_dcrs(
    search: str | None = None,
    type: str | None = None,
    status: str | None = None,
    critical: str | None = None,
    office: str | None = None,
    customer: str | None = None,
) -> list[DCR]:
    q = (search or "").strip().lower()
    out = []
    for r in store.all():
        if status != "Draft" and r.status == "Draft":
            continue  # drafts are reviewed in the inbox, not listed as records
        if status and r.status != status:
            continue
        if type and r.type != type:
            continue
        if critical and (r.critical if r.critical in ("Y", "N") else "N/A") != critical:
            continue
        if office and r.amex_office != office:
            continue
        if customer and r.customer != customer:
            continue
        if q:
            hay = " ".join(
                str(v) for v in (r.tracking_number, r.customer, r.supplier, r.project, r.category,
                                 r.description, r.responsible_party_name) if v
            ).lower()
            if q not in hay:
                continue
        out.append(r)
    return _sort_newest(out)


@router.get("/tracker.xlsx")
def download_tracker() -> FileResponse:
    """The filled SOP 5-A1 tracker workbook itself."""
    return FileResponse(
        TRACKER_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"DCR_Tracker_{date.today().isoformat()}.xlsx",
    )


@router.get("/dcrs/{dcr_id}", response_model=DCR)
def get_dcr(dcr_id: str) -> DCR:
    rec = store.get(dcr_id)
    if not rec:
        raise HTTPException(404, f"DCR {dcr_id} not found")
    return rec


def _clean(update: BaseModel) -> dict:
    return {
        k: (v.strip() if isinstance(v, str) and v.strip() else None)
        for k, v in update.model_dump(exclude_unset=True).items()
    }


@router.post("/dcrs", response_model=DCR)
def create_dcr(entry: DCRUpdate) -> DCR:
    """Manual "New entry": gets the next DCR number and is written to the Excel tracker."""
    values = _clean(entry)
    if not values.get("description"):
        raise HTTPException(400, "Description of the issue is required")
    try:
        return store.create(values, values.get("entered_by"))
    except WorkbookLockedError as e:
        raise _locked(e)


@router.patch("/dcrs/{dcr_id}", response_model=DCR)
def update_dcr(dcr_id: str, update: DCRUpdate) -> DCR:
    if not store.get(dcr_id):
        raise HTTPException(404, f"DCR {dcr_id} not found")
    try:
        return store.update(dcr_id, _clean(update))
    except WorkbookLockedError as e:
        raise _locked(e)


class ConfirmRequest(BaseModel):
    entered_by: str | None = None


@router.post("/dcrs/{dcr_id}/confirm", response_model=DCR)
def confirm_dcr(dcr_id: str, body: ConfirmRequest) -> DCR:
    """Accept an e-mail draft: next YY-NNN number + new row in the Excel tracker."""
    if not store.get(dcr_id):
        raise HTTPException(404, f"DCR {dcr_id} not found")
    try:
        return store.confirm(dcr_id, body.entered_by)
    except WorkbookLockedError as e:
        raise _locked(e)


# ---------------------------------------------------------------- e-mails


class RawEmail(BaseModel):
    raw: str
    auto_add: bool = False
    entered_by: str | None = None


def _ingest(data: bytes, auto_add: bool, entered_by: str | None) -> dict:
    try:
        return store.ingest(data, auto_add=auto_add, entered_by=entered_by)
    except WorkbookLockedError as e:
        raise _locked(e)


@router.post("/emails")
def ingest_email(email: RawEmail) -> dict:
    """Paste a raw e-mail (with or without headers)."""
    if not email.raw.strip():
        raise HTTPException(400, "Empty e-mail")
    return _ingest(email.raw.encode("utf-8"), email.auto_add, email.entered_by)


@router.post("/emails/upload")
async def upload_emails(
    files: list[UploadFile] = File(...), auto_add: bool = Form(False), entered_by: str | None = Form(None)
) -> list[dict]:
    """Upload .eml / .msg / .txt files."""
    return [{"file": f.filename, **_ingest(await f.read(), auto_add, entered_by)} for f in files]


@router.get("/emails/samples")
def list_samples() -> list[dict]:
    known = {e.message_id for r in store.all() for e in r.source_emails}
    known |= {m["message_id"] for m in store.ignored_emails}
    out = []
    for p in store.sample_emails():
        e = parse_any(p.read_bytes())
        out.append({"name": p.name, "subject": e.subject, "sender": e.sender, "date": e.date,
                    "processed": e.message_id in known})
    return out


@router.post("/emails/samples/{name}")
def ingest_sample(name: str, auto_add: bool = False, entered_by: str | None = None) -> dict:
    path = next((p for p in store.sample_emails() if p.name == name), None)
    if not path:
        raise HTTPException(404, f"Sample '{name}' not found")
    return {"file": name, **_ingest(path.read_bytes(), auto_add, entered_by)}


@router.get("/emails/ignored")
def ignored_emails() -> list[dict]:
    return store.ignored_emails


# ---------------------------------------------------------------- admin


@router.post("/admin/reload")
def reload() -> dict:
    """Re-read the Excel tracker (e.g. after it was edited in Excel)."""
    store.load()
    return {"records": len(_confirmed())}


@router.post("/admin/reset")
def reset() -> dict:
    """Fresh copy of the template workbook; drops drafts and e-mail history."""
    store.reset()
    return {"records": len(_confirmed())}
