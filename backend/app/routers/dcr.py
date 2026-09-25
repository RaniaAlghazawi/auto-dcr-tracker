"""DCR tracker API: dashboard, records, drafts and the Excel tracker download."""

from collections import Counter
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.dcr.excel_writer import WorkbookLockedError
from app.dcr.extractor import CLAUDE_MODEL, use_claude
from app.dcr.normalize import parse_financial, parse_iso
from app.dcr.schema import CATEGORIES, DCR, DCR_TYPES, OFFICES, RESPONSIBLE_PARTIES, DCRUpdate
from app.dcr.store import TRACKER_PATH, store

router = APIRouter(prefix="/api", tags=["dcr"])


def _locked(e: WorkbookLockedError) -> HTTPException:
    return HTTPException(409, str(e))


def _confirmed() -> list[DCR]:
    """Entries in the Excel tracker; drafts from the wizard are not counted until confirmed."""
    return [r for r in store.all() if r.status != "Draft"]


def _sort_newest(records: list[DCR]) -> list[DCR]:
    return sorted(records, key=lambda r: (r.occurred_on or "", r.tracking_number or ""), reverse=True)


# ---------------------------------------------------------------- meta & dashboard


@router.get("/meta")
def meta() -> dict:
    confirmed = _confirmed()
    # one entry per customer regardless of spelling case ("Chemonics" / "CHEMONICS"); most frequent spelling wins
    spellings = Counter(r.customer.strip() for r in confirmed if r.customer and r.customer != "N/A")
    by_key: dict[str, str] = {}
    for name, _ in spellings.most_common():
        by_key.setdefault(name.lower(), name)
    customers = sorted(by_key.values(), key=str.lower)
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


OVERDUE_DAYS = 60  # SOP 5 threshold, same as quality.OPEN_TOO_LONG_DAYS
TOP_N = 8


def _is_overdue(r: DCR, today: date) -> bool:
    """Open and occurred more than OVERDUE_DAYS ago (the "Overdue" tile)."""
    occurred = parse_iso(r.occurred_on)
    return r.status == "Open" and occurred is not None and (today - occurred).days > OVERDUE_DAYS


def _eur_impact(r: DCR, year: int) -> float:
    """EUR financial impact of a case that occurred in `year` (the "financial impact" tile), else 0."""
    if not (r.occurred_on or "").startswith(str(year)):
        return 0.0
    amount, currency = parse_financial(r.financial_impact)
    return amount if currency == "EUR" else 0.0


def _top_open_by(records: list[DCR], field: str) -> list[dict]:
    """Open cases per supplier/customer, case-insensitive; most frequent spelling is shown."""
    groups: dict[str, Counter] = {}
    for r in records:
        value = (getattr(r, field) or "").strip()
        if r.status != "Open" or not value or value == "N/A":
            continue
        groups.setdefault(value.lower(), Counter())[value] += 1
    rows = [{"name": c.most_common(1)[0][0], "count": sum(c.values())} for c in groups.values()]
    return sorted(rows, key=lambda x: (-x["count"], x["name"].lower()))[:TOP_N]


@router.get("/dashboard")
def dashboard(year: int | None = None) -> dict:
    """KPIs cover the whole tracker; the charts follow the optional `year` filter (year occurred)."""
    recs = _confirmed()
    today = date.today()
    open_recs = [r for r in recs if r.status == "Open"]

    ytd_eur = sum(_eur_impact(r, today.year) for r in recs)

    charted = [r for r in recs if not year or (r.occurred_on or "").startswith(str(year))]
    by_type = Counter(r.type for r in charted if r.type)
    by_category = Counter(r.category or "Other" for r in charted)
    years = sorted({int(r.occurred_on[:4]) for r in recs if parse_iso(r.occurred_on)})

    attention = sorted((r for r in open_recs if r.critical == "Y"), key=lambda r: r.occurred_on or "")[:7]

    return {
        "year": today.year,
        "filter_year": year,
        "years": [y for y in years if y >= today.year - 2],  # year pills: last three years
        "kpis": {
            "total": len(recs),
            "open": len(open_recs),
            "overdue": sum(_is_overdue(r, today) for r in open_recs),
            "financial_ytd_eur": round(ytd_eur, 2),
            "critical_open": sum(r.critical == "Y" for r in open_recs),
            "capa_pending": sum(r.capa_needed == "Y" for r in open_recs),
            "drafts": sum(r.status == "Draft" for r in store.all()),
        },
        "by_type": [{"name": t, "count": by_type.get(t, 0)} for t in DCR_TYPES],
        "by_category": [{"name": k, "count": v} for k, v in by_category.most_common(TOP_N)],
        "open_by_supplier": _top_open_by(charted, "supplier"),
        "open_by_customer": _top_open_by(charted, "customer"),
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
    overdue: bool | None = None,
    financial_year: int | None = None,
) -> list[DCR]:
    """Records list. `overdue` and `financial_year` match the dashboard tiles of the same name."""
    q = (search or "").strip().lower()
    today = date.today()
    out = []
    for r in store.all():
        if status and r.status != status:
            continue
        if overdue and not _is_overdue(r, today):
            continue
        if financial_year and _eur_impact(r, financial_year) <= 0:
            continue
        if type and r.type != type:
            continue
        if critical and (r.critical if r.critical in ("Y", "N") else "N/A") != critical:
            continue
        if office and r.amex_office != office:
            continue
        if customer and (r.customer or "").strip().lower() != customer.strip().lower():
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
    """Manual entry: gets the next DCR number and is written to the Excel tracker."""
    values = _clean(entry)
    if not values.get("description"):
        raise HTTPException(400, "Description of the issue is required")
    try:
        return store.create(values)
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
    """Accept a draft (e.g. filled by the "From project" wizard): next DCR number + new Excel row."""
    if not store.get(dcr_id):
        raise HTTPException(404, f"DCR {dcr_id} not found")
    try:
        return store.confirm(dcr_id, body.entered_by)
    except WorkbookLockedError as e:
        raise _locked(e)


# ---------------------------------------------------------------- admin


@router.post("/admin/reload")
def reload() -> dict:
    """Re-read the Excel tracker (e.g. after it was edited in Excel)."""
    store.load()
    return {"records": len(_confirmed())}


@router.post("/admin/reset")
def reset() -> dict:
    """Fresh copy of the template workbook; drops drafts and e-mail links."""
    store.reset()
    return {"records": len(_confirmed())}
