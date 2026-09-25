"""DCR store. The tracker workbook is the source of truth.

- DCRs live in the Excel tracker (resources/output/DCR_Tracker.xlsx, a working copy of
  resources/template_SOP.xlsx, or DCR_TRACKER_PATH). They are read from it on start and written back
  row by row when added or edited.
- The e-mails behind an entry (read from its project folder in resources/) are kept in
  resources/data/dcr_state.json, keyed by DCR number, because the tracker has no column for them.
"""

import json
import logging
import os
import threading
from datetime import date
from pathlib import Path

from app.dcr import quality
from app.dcr.excel_writer import ensure_working_copy, write_rows
from app.dcr.extractor import extract
from app.dcr.master_data import build_master_data
from app.dcr.project_emails import RESOURCES_DIR, find_project_dirs, load_project_emails
from app.dcr.schema import DCR, SourceEmail
from app.dcr.tracker_import import COLUMNS, import_tracker
from app.resources import resource_path

log = logging.getLogger(__name__)

TEMPLATE_PATH = resource_path("template_SOP.xlsx")
TRACKER_PATH = Path(os.getenv("DCR_TRACKER_PATH") or resource_path("output", "DCR_Tracker.xlsx"))
STATE_PATH = resource_path("data", "dcr_state.json")

# Tracker columns Claude fills from the e-mails (the reviewer can change all of them before saving)
EXTRACTED_FIELDS = [
    "type", "category", "critical", "occurred_on", "amex_office", "pharma", "supplier", "customer",
    "project", "responsible_party", "responsible_party_name", "description", "root_cause",
    "financial_impact", "actions_taken", "capa_needed", "closure_date",
]
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
            if STATE_PATH.exists():
                self.email_links = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("email_links", {})
            self.records = {}
            for rec in import_tracker(TRACKER_PATH):
                meta = self.email_links.get(rec.tracking_number)
                if meta:
                    rec.source = "email"
                    for k, v in meta.items():
                        setattr(rec, k, [SourceEmail(**e) for e in v] if k == "source_emails" else v)
                self.records[rec.id] = rec
            self.refresh_issues()
            log.info("Loaded %d DCRs from %s", len(self.records), TRACKER_PATH.name)

    def save_state(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps({"email_links": self.email_links}, indent=1, ensure_ascii=False), encoding="utf-8")

    def reset(self) -> None:
        """Start over: fresh copy of the template workbook, no linked e-mails."""
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

    # ------------------------------------------------------------ project e-mails
    def read_project(self, project: str) -> dict:
        """Read the project's e-mail folder and let Claude propose the tracker fields (nothing is saved)."""
        folders = find_project_dirs(project)
        emails, skipped = load_project_emails(project)
        result = {
            "project": project,
            "folders": [f.relative_to(RESOURCES_DIR).as_posix() for f in folders],
            "emails": [{"subject": e.subject, "sender": e.sender, "date": e.date, "attachments": e.attachments} for e in emails],
            "skipped": skipped,
            "fields": {},
            "method": None,
            "is_dcr": None,
            "missing_information": [],
        }
        if not emails:
            return result
        ex, method = extract(emails, build_master_data(self.all()))
        fields = {f: getattr(ex, f) for f in EXTRACTED_FIELDS if getattr(ex, f) not in (None, "")}
        fields.setdefault("project", project)
        result.update(
            fields=fields,
            method=method,
            is_dcr=ex.is_dcr,
            title=ex.title,
            requested_actions=ex.requested_actions or None,
            reported_by_party=ex.reported_by_party or None,
            freight_forwarder=ex.freight_forwarder or None,
            missing_information=ex.missing_information,
        )
        return result

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
            rec.status = "Closed" if rec.closure_date else "Open"
            try:
                self._write(rec)
            except Exception:
                self.records[dcr_id] = before
                raise
            rec.issues = quality.check(rec)
            self.save_state()
            return rec

    def create(self, values: dict, source_project: str | None = None, email_meta: dict | None = None) -> DCR:
        """New entry: next DCR number, written as a new row to the Excel tracker.

        source_project links the e-mails of that project folder to the entry.
        """
        with self._lock:
            rec = DCR(id="new", **values)
            if source_project:
                emails, _ = load_project_emails(source_project)
                rec.source_emails = [SourceEmail(**e.model_dump(include=set(SourceEmail.model_fields))) for e in emails]
                rec.source = "email" if emails else "tracker"
                for k, v in (email_meta or {}).items():
                    if k in EMAIL_META and v:
                        setattr(rec, k, v)
            rec.tracking_number = self.next_tracking_number()
            rec.id = f"T-{rec.tracking_number}"
            rec.status = "Closed" if rec.closure_date else "Open"
            self._write(rec)
            self.records[rec.id] = rec
            rec.issues = quality.check(rec)
            self.save_state()
            return rec


store = Store()

