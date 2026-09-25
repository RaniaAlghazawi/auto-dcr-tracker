"""DCR store. The tracker workbook is the source of truth.

- DCRs live in the Excel tracker (resources/output/DCR_Tracker.xlsx, a working copy of
  resources/template_SOP.xlsx, or DCR_TRACKER_PATH). They are read from it on start and written back
  row by row when added or edited.
- Drafts (entries the "From project" wizard filled from a project's e-mails, awaiting review) and
  the e-mails behind each entry are kept in resources/data/dcr_state.json, because the tracker has
  no columns for them. A draft gets its DCR number and Excel row when it is confirmed.
"""

import json
import logging
import os
import threading
from datetime import date
from pathlib import Path

from app.dcr import quality
from app.dcr.excel_writer import ensure_working_copy, write_rows
from app.dcr.schema import DCR, SourceEmail
from app.dcr.tracker_import import COLUMNS, import_tracker
from app.resources import resource_path

log = logging.getLogger(__name__)

TEMPLATE_PATH = resource_path("template_SOP.xlsx")
TRACKER_PATH = Path(os.getenv("DCR_TRACKER_PATH") or resource_path("output", "DCR_Tracker.xlsx"))
STATE_PATH = resource_path("data", "dcr_state.json")

EMAIL_META = ["source_emails", "extraction_method", "reported_by_party", "freight_forwarder", "requested_actions"]


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.records: dict[str, DCR] = {}
        self.email_links: dict[str, dict] = {}  # DCR number -> EMAIL_META of that entry

    # ------------------------------------------------------------ persistence
    def load(self) -> None:
        """(Re-)read the Excel tracker and the app state. Also picks up edits made directly in Excel."""
        with self._lock:
            ensure_working_copy(TEMPLATE_PATH, TRACKER_PATH)
            drafts: list[DCR] = []
            if STATE_PATH.exists():
                state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                self.email_links = state.get("email_links", {})
                drafts = [DCR(**d) for d in state.get("drafts", [])]
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
        }
        STATE_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    def reset(self) -> None:
        """Start over: fresh copy of the template workbook, no drafts, no linked e-mails."""
        with self._lock:
            TRACKER_PATH.unlink(missing_ok=True)
            STATE_PATH.unlink(missing_ok=True)
            self.email_links = {}
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

    # ------------------------------------------------------------ Excel
    def _write(self, rec: DCR) -> None:
        [row] = write_rows(TRACKER_PATH, [(rec.excel_row, {c: getattr(rec, c) for c in COLUMNS})])
        rec.excel_row = row
        if rec.source == "email" and rec.tracking_number:
            self.email_links[rec.tracking_number] = {
                k: ([e.model_dump() for e in rec.source_emails] if k == "source_emails" else getattr(rec, k))
                for k in EMAIL_META
            }

    # ------------------------------------------------------------ edits
    def update(self, dcr_id: str, changes: dict) -> DCR:
        with self._lock:
            rec = self.records[dcr_id]
            before = rec.model_copy(deep=True)
            for field, value in changes.items():
                setattr(rec, field, value)
            if rec.status != "Draft":  # drafts reach Excel only when confirmed
                rec.status = "Closed" if rec.closure_date else "Open"
                try:
                    self._write(rec)
                except Exception:
                    self.records[dcr_id] = before
                    raise
            rec.issues = quality.check(rec)
            self.save_state()
            return rec

    def _next_draft_id(self) -> str:
        used = [int(k[2:]) for k in self.records if k.startswith("E-") and k[2:].isdigit()]
        return f"E-{(max(used) + 1 if used else 1):04d}"

    def confirm(self, dcr_id: str, entered_by: str | None) -> DCR:
        """Accept a draft: assign the next DCR number and add it as a row to the Excel tracker."""
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

    def create(self, values: dict) -> DCR:
        """Manual new entry: next DCR number, written as a new row to the Excel tracker."""
        with self._lock:
            rec = DCR(id=self._next_draft_id(), status="Draft", **values)
            self.records[rec.id] = rec
            try:
                return self.confirm(rec.id, values.get("entered_by"))
            except Exception:
                del self.records[rec.id]
                raise

store = Store()

