"""DCR store. The tracker workbook is the source of truth for confirmed entries.

- Confirmed DCRs live in the Excel tracker (resources/output/DCR_Tracker.xlsx, a working copy of
  resources/template_SOP.xlsx, or DCR_TRACKER_PATH). They are read from it on start and written back
  row by row when added or edited.
- Drafts (e-mail extractions awaiting review), the e-mails behind each DCR and ignored e-mails are kept
  in resources/data/dcr_state.json because the tracker has no columns for them.
"""

import json
import logging
import os
import threading
from datetime import date
from pathlib import Path

from app.dcr import quality
from app.dcr.email_parser import NO_SUBJECT, ParsedEmail, domain_of, normalize_subject, parse_any
from app.dcr.excel_writer import ensure_working_copy, write_rows
from app.dcr.extractor import Extraction, extract
from app.dcr.master_data import build_master_data
from app.dcr.schema import DCR, SourceEmail
from app.dcr.tracker_import import COLUMNS, import_tracker
from app.resources import resource_path

log = logging.getLogger(__name__)

TEMPLATE_PATH = resource_path("template_SOP.xlsx")
TRACKER_PATH = Path(os.getenv("DCR_TRACKER_PATH") or resource_path("output", "DCR_Tracker.xlsx"))
STATE_PATH = resource_path("data", "dcr_state.json")
SAMPLE_EMAILS_DIR = resource_path("sample_emails")

# Extracted fields a follow-up e-mail may fill in on an already confirmed DCR (never overwrites)
FILLABLE = [
    "type", "category", "critical", "occurred_on", "amex_office", "pharma", "supplier", "customer",
    "project", "responsible_party", "responsible_party_name", "description", "root_cause",
    "financial_impact", "actions_taken", "capa_needed", "closure_date",
]
EMAIL_META = ["source_emails", "extraction_method", "reported_by_party", "freight_forwarder", "requested_actions"]


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.records: dict[str, DCR] = {}
        self.email_links: dict[str, dict] = {}  # tracking number -> EMAIL_META of that DCR
        self.ignored_emails: list[dict] = []

    # ------------------------------------------------------------ persistence
    def load(self) -> None:
        """(Re-)read the Excel tracker and the app state. Also picks up edits made directly in Excel."""
        with self._lock:
            ensure_working_copy(TEMPLATE_PATH, TRACKER_PATH)
            drafts: list[DCR] = []
            if STATE_PATH.exists():
                state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                drafts = [DCR(**d) for d in state.get("drafts", [])]
                self.email_links = state.get("email_links", {})
                self.ignored_emails = state.get("ignored_emails", [])
            self.records = {}
            for rec in import_tracker(TRACKER_PATH):
                meta = self.email_links.get(rec.tracking_number)
                if meta:
                    rec.source = "email"
                    for k, v in meta.items():
                        setattr(rec, k, [SourceEmail(**e) for e in v] if k == "source_emails" else v)
                self.records[rec.id] = rec
            for d in drafts:
                self.records[d.id] = d
            self.refresh_issues()
            log.info("Loaded %d DCRs from %s (+%d drafts)", len(self.records) - len(drafts), TRACKER_PATH.name, len(drafts))

    def save_state(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "drafts": [r.model_dump() for r in self.records.values() if r.status == "Draft"],
            "email_links": self.email_links,
            "ignored_emails": self.ignored_emails,
        }
        STATE_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    def reset(self) -> None:
        """Start over: fresh copy of the template workbook, no drafts, no e-mail history."""
        with self._lock:
            TRACKER_PATH.unlink(missing_ok=True)
            STATE_PATH.unlink(missing_ok=True)
            self.email_links, self.ignored_emails = {}, []
            self.load()

    # ------------------------------------------------------------ queries
    def refresh_issues(self) -> None:
        today = date.today()
        for rec in self.records.values():
            rec.issues = quality.check(rec, today)

    def all(self) -> list[DCR]:
        return list(self.records.values())

    def get(self, dcr_id: str) -> DCR | None:
        return self.records.get(dcr_id)

    def next_tracking_number(self) -> str:
        yy = f"{date.today().year % 100:02d}"
        numbers = [
            int(r.tracking_number.split("-")[1])
            for r in self.records.values()
            if r.tracking_number and r.tracking_number.startswith(yy + "-") and r.tracking_number.split("-")[1].isdigit()
        ]
        return f"{yy}-{(max(numbers) + 1 if numbers else 1):03d}"

    def sample_emails(self) -> list[Path]:
        if not SAMPLE_EMAILS_DIR.exists():
            return []
        return sorted(p for p in SAMPLE_EMAILS_DIR.iterdir() if p.suffix.lower() in (".eml", ".msg", ".txt"))

    # ------------------------------------------------------------ Excel
    def _write(self, rec: DCR) -> None:
        [row] = write_rows(TRACKER_PATH, [(rec.excel_row, {c: getattr(rec, c) for c in COLUMNS})])
        rec.excel_row = row
        if rec.source == "email" and rec.tracking_number:
            self.email_links[rec.tracking_number] = {
                k: ([e.model_dump() for e in rec.source_emails] if k == "source_emails" else getattr(rec, k))
                for k in EMAIL_META
            }

    # ------------------------------------------------------------ e-mail ingestion
    def _find_thread(self, email: ParsedEmail) -> DCR | None:
        ids = {i for i in [email.in_reply_to, *email.references] if i}
        if ids:
            for rec in self.records.values():
                if any(src.message_id in ids for src in rec.source_emails):
                    return rec
        subject = email.thread_subject
        if not subject or subject == NO_SUBJECT:
            return None
        for rec in self.records.values():
            if rec.source_emails and normalize_subject(rec.source_emails[0].subject) == subject:
                return rec
        return None

    def ingest(self, data: bytes, auto_add: bool = False, entered_by: str | None = None) -> dict:
        """Parse an e-mail, attach it to its DCR thread or create a new draft.

        auto_add: write a new DCR straight into the Excel tracker instead of leaving a draft for review.
        """
        with self._lock:
            email = parse_any(data)
            known = {src.message_id for r in self.records.values() for src in r.source_emails}
            known |= {m["message_id"] for m in self.ignored_emails}
            if email.message_id in known:
                return {"result": "duplicate", "subject": email.subject}

            existing = self._find_thread(email)
            thread = [_to_parsed(s) for s in existing.source_emails] + [email] if existing else [email]
            extraction, method = extract(thread, build_master_data(self.all()))

            if not existing and not extraction.is_dcr:
                self.ignored_emails.append(
                    {"message_id": email.message_id, "sender": email.sender, "subject": email.subject,
                     "date": email.date, "method": method}
                )
                self.save_state()
                return {"result": "not_dcr", "subject": email.subject, "method": method}

            src = SourceEmail(**email.model_dump(include=set(SourceEmail.model_fields)))
            if existing:
                rec = existing
                rec.source_emails.append(src)
                if rec.status == "Draft":
                    _apply_extraction(rec, extraction, method, overwrite=True)
                    result = "updated"
                else:
                    # confirmed entry: only fill what is still empty, then update its Excel row
                    _apply_extraction(rec, extraction, method, overwrite=False)
                    rec.status = "Closed" if rec.closure_date else "Open"
                    self._write(rec)
                    result = "attached"
            else:
                rec = DCR(id=self._next_draft_id(), status="Draft", source="email", source_emails=[src])
                _apply_extraction(rec, extraction, method, overwrite=True)
                self.records[rec.id] = rec
                result = "created"

            rec.issues = quality.check(rec)
            self.save_state()
            out = {"result": result, "id": rec.id, "subject": email.subject, "method": method,
                   "tracking_number": rec.tracking_number}
            if result == "created" and auto_add:
                confirmed = self.confirm(rec.id, entered_by)
                out.update(result="added", id=confirmed.id, tracking_number=confirmed.tracking_number)
            return out

    def _next_draft_id(self) -> str:
        used = [int(k[2:]) for k in self.records if k.startswith("E-") and k[2:].isdigit()]
        return f"E-{(max(used) + 1 if used else 1):04d}"

    # ------------------------------------------------------------ edits
    def confirm(self, dcr_id: str, entered_by: str | None) -> DCR:
        """Accept a draft: assign the next tracking number and add it as a row to the Excel tracker."""
        with self._lock:
            rec = self.records[dcr_id]
            if rec.status != "Draft":
                return rec
            rec.tracking_number = self.next_tracking_number()
            if entered_by and not rec.entered_by:
                rec.entered_by = entered_by
            rec.status = "Closed" if rec.closure_date else "Open"
            try:
                self._write(rec)
            except Exception:
                rec.tracking_number, rec.status = None, "Draft"
                raise
            del self.records[dcr_id]
            rec.id = f"T-{rec.tracking_number}"
            self.records[rec.id] = rec
            rec.issues = quality.check(rec)
            self.save_state()
            return rec

    def update(self, dcr_id: str, changes: dict) -> DCR:
        with self._lock:
            rec = self.records[dcr_id]
            before = rec.model_copy(deep=True)
            for field, value in changes.items():
                setattr(rec, field, value)
            if rec.status != "Draft":
                rec.status = "Closed" if rec.closure_date else "Open"
                try:
                    self._write(rec)
                except Exception:
                    self.records[dcr_id] = before
                    raise
            rec.issues = quality.check(rec)
            self.save_state()
            return rec

    def create(self, values: dict, entered_by: str | None) -> DCR:
        """A manual "New entry" — goes straight into the Excel tracker."""
        with self._lock:
            rec = DCR(id=self._next_draft_id(), status="Draft", source="tracker", **values)
            self.records[rec.id] = rec
            try:
                return self.confirm(rec.id, entered_by)
            except Exception:
                del self.records[rec.id]
                raise


def _to_parsed(src: SourceEmail) -> ParsedEmail:
    return ParsedEmail(**src.model_dump(), sender_domain=domain_of(src.sender))


def _apply_extraction(rec: DCR, ex: Extraction, method: str, overwrite: bool) -> None:
    for field in FILLABLE:
        value = getattr(ex, field, None)
        if value in (None, ""):
            continue
        if overwrite or getattr(rec, field) in (None, "", "N/A"):
            setattr(rec, field, value)
    for field in ("freight_forwarder", "reported_by_party", "requested_actions"):
        value = getattr(ex, field, None)
        if value and (overwrite or not getattr(rec, field)):
            setattr(rec, field, value)
    rec.extraction_method = method


store = Store()
