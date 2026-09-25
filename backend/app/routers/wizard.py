"""New DCR entry wizard - project-based entry creation.

Ask for one thing -- the project number -- then read that project's
correspondence and fill the entry in. The person edits and approves; they never
type the record from scratch.

If a project has no correspondence on file, an empty entry is created so the
record can still be logged inside the SOP's 3-day deadline.
"""

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dcr.email_parser import parse_any
from app.dcr.extractor import extract, Extraction
from app.dcr.master_data import build_master_data
from app.dcr.projects import find_project_dir, known_projects, summarise
from app.dcr.store import store

router = APIRouter(prefix="/api/wizard", tags=["wizard"])

PROJECT_NUMBER = re.compile(r"\b(20\d{6})\b")


@dataclass
class JobState:
    running: bool = False
    done: int = 0
    total: int = 0
    current: str = ""
    engine: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    results: list[dict] = field(default_factory=list)

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "done": self.done,
            "total": self.total,
            "current": self.current,
            "engine": self.engine,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "results": list(self.results),
            "percent": int(self.done / self.total * 100) if self.total else 0,
        }


STATE = JobState()
_LOCK = threading.Lock()


class ProjectSuggestion(BaseModel):
    number: str
    status: str  # "new", "draft", "recorded"
    dcr_number: Optional[str] = None


class WizardStartResponse(BaseModel):
    suggestions: list[ProjectSuggestion]
    engine: str
    pending_drafts: int


class WizardSubmitRequest(BaseModel):
    project: str
    force: bool = False


class WizardWorkingResponse(BaseModel):
    project: str
    info: dict
    engine: str
    pending_drafts: int


class NotADCRResponse(BaseModel):
    project: str
    reason: str
    summary: str
    emails: int
    pending_drafts: int


# --------------------------------------------------------------------- helpers

def _existing(project: str) -> Optional[dict]:
    """Check if a project already has a DCR record."""
    for rec in store.all():
        if rec.project == project and rec.status != "Rejected":
            return {
                "id": rec.id,
                "dcr_number": rec.tracking_number,
                "is_draft": rec.status == "Draft",
            }
    return None


def _project_options() -> list[ProjectSuggestion]:
    """Known projects, annotated with whether they already have a DCR."""
    covered = {
        row["project"]: row
        for row in [_existing(p) for p in known_projects()]
        if row is not None
    }
    options = []
    for number in known_projects():
        row = covered.get(number)
        options.append(ProjectSuggestion(
            number=number,
            status="draft" if row and row["is_draft"] else "recorded" if row else "new",
            dcr_number=row["dcr_number"] if row else None,
        ))
    return options


def _blank_entry(project: str, entered_by: Optional[str] = None) -> dict:
    """No correspondence to read -- start an empty editable draft."""
    from app.dcr.schema import DCR

    rec = DCR(
        id=store._next_draft_id(),
        status="Draft",
        source="tracker",
        project=project,
        entered_by=entered_by or "manual",
        description=f"Manual entry for project {project} - no correspondence on file",
    )
    store.records[rec.id] = rec
    store.save_state()

    return {
        "result": "created",
        "id": rec.id,
        "message": f"No correspondence found for project {project}, so this entry is blank. "
                   "Fill in what you know — you can press Update later to pull in emails.",
    }


def _compile_project(project: str, entered_by: Optional[str] = None) -> dict:
    """Compile a DCR from project correspondence."""
    directory = find_project_dir(project)
    if not directory:
        return _blank_entry(project, entered_by)

    # Read all emails from the project directory
    files = sorted(directory.glob("**/*.msg"))
    emails = []
    for file_path in files:
        try:
            email = parse_any(file_path.read_bytes())
            emails.append(email)
        except Exception:
            continue

    if not emails:
        return _blank_entry(project, entered_by)

    # Extract DCR information from emails
    master_data = build_master_data(store.all())
    extraction, method = extract(emails, master_data)

    if not extraction.is_dcr:
        return {
            "result": "not_a_dcr",
            "project": project,
            "reason": extraction.missing_information[0] if extraction.missing_information else "No quality issue found.",
            "summary": extraction.title,
            "emails": len(emails),
            "method": method,
        }

    # Create a draft DCR from the extraction
    from app.dcr.schema import DCR, SourceEmail

    source_emails = [SourceEmail(**e.model_dump()) for e in emails]

    rec = DCR(
        id=store._next_draft_id(),
        status="Draft",
        source="email",
        source_emails=source_emails,
        project=project,
        type=extraction.type,
        category=extraction.category,
        critical=extraction.critical,
        occurred_on=extraction.occurred_on,
        amex_office=extraction.amex_office,
        pharma=extraction.pharma,
        supplier=extraction.supplier,
        customer=extraction.customer,
        responsible_party=extraction.responsible_party,
        responsible_party_name=extraction.responsible_party_name,
        description=extraction.description,
        root_cause=extraction.root_cause,
        financial_impact=extraction.financial_impact,
        actions_taken=extraction.actions_taken,
        capa_needed=extraction.capa_needed,
        closure_date=extraction.closure_date,
        entered_by=entered_by or "ingest",
        extraction_method=method,
        freight_forwarder=extraction.freight_forwarder,
        reported_by_party=extraction.reported_by_party,
        requested_actions=extraction.requested_actions,
    )

    store.records[rec.id] = rec
    store.save_state()

    return {
        "result": "drafted",
        "id": rec.id,
        "project": project,
        "method": method,
    }


def _worker(project: str, force: bool, entered_by: Optional[str]) -> None:
    """Background worker to compile project."""
    try:
        from app.dcr.extractor import use_claude

        STATE.engine = "claude" if use_claude() else "rule"
        STATE.total = 1
        STATE.current = project

        result = _compile_project(project, entered_by)

        STATE.results.append({
            "project": project,
            "status": result.get("result", "error"),
            "reason": result.get("reason", ""),
            "summary": result.get("summary", ""),
            "emails": result.get("emails", 0),
            "dcr_id": result.get("id"),
        })
        STATE.done += 1
        STATE.current = ""
    except Exception as exc:
        STATE.results.append({
            "project": project,
            "status": "error",
            "reason": f"{type(exc).__name__}: {exc}",
        })
        STATE.done += 1
        STATE.current = ""
    finally:
        STATE.running = False
        STATE.finished_at = datetime.now().strftime("%H:%M:%S")


def start_job(project: str, force: bool = False, entered_by: Optional[str] = None) -> bool:
    """Begin a compile job. Returns False if one is already going."""
    with _LOCK:
        if STATE.running:
            return False
        STATE.running = True
        STATE.done = 0
        STATE.total = 0
        STATE.current = ""
        STATE.results = []
        STATE.started_at = datetime.now().strftime("%H:%M:%S")
        STATE.finished_at = None

    threading.Thread(
        target=_worker, args=(project, force, entered_by),
        name="dcr-wizard", daemon=True,
    ).start()
    return True


# --------------------------------------------------------------------- routes

@router.get("/", response_model=WizardStartResponse)
def wizard_start():
    """Start page with project suggestions."""
    from app.dcr.extractor import use_claude

    return WizardStartResponse(
        suggestions=_project_options(),
        engine="claude" if use_claude() else "rule",
        pending_drafts=sum(1 for r in store.all() if r.status == "Draft"),
    )


@router.post("/")
def wizard_submit(request: WizardSubmitRequest, entered_by: Optional[str] = None):
    """Submit project number to start compilation."""
    project = request.project.strip()

    if not project:
        raise HTTPException(400, "Enter the project number this DCR relates to.")

    # Already covered? Send them to it rather than making a duplicate.
    existing = _existing(project)
    if existing and not request.force:
        if existing["is_draft"]:
            return {
                "result": "existing_draft",
                "message": f"Project {project} already has a draft waiting for review.",
                "dcr_id": existing["id"],
            }
        return {
            "result": "existing_record",
            "message": f"Project {project} is already recorded as {existing['dcr_number']}. "
                     "Use Update from emails to pull in anything new.",
            "dcr_id": existing["id"],
        }

    if find_project_dir(project) is None:
        # No project directory - create blank entry
        result = _blank_entry(project, entered_by)
        return result

    # Start background compilation
    if not start_job(project, request.force, entered_by):
        raise HTTPException(409, "A compilation job is already running")

    return {"result": "started", "project": project}


@router.get("/working/{project}", response_model=WizardWorkingResponse)
def wizard_working(project: str):
    """Working page with progress information."""
    from app.dcr.extractor import use_claude

    info = summarise(project)
    return WizardWorkingResponse(
        project=project,
        info={
            "email_count": info.email_count,
            "thread_count": info.thread_count,
            "parties": [{"name": name, "count": count} for name, count in info.parties],
        },
        engine="claude" if use_claude() else "rule",
        pending_drafts=sum(1 for r in store.all() if r.status == "Draft"),
    )


@router.get("/working/{project}/status")
def wizard_working_status(project: str):
    """Progress for the waiting page, plus where to go when it finishes."""
    state = STATE.snapshot()
    payload = dict(state)

    if not state["running"]:
        result = next(
            (r for r in state.get("results", []) if r["project"] == project), None
        )
        payload["outcome"] = result["status"] if result else None
        payload["reason"] = result["reason"] if result else None

        if result and result.get("dcr_id"):
            payload["next_url"] = f"/detail/{result['dcr_id']}"
        elif result and result["status"] == "not_a_dcr":
            payload["next_url"] = f"/wizard/not-a-dcr/{project}"
    return payload


@router.get("/not-a-dcr/{project}", response_model=NotADCRResponse)
def wizard_not_a_dcr(project: str):
    """Claude read the project and found no quality issue."""
    state = STATE.snapshot()
    result = next(
        (r for r in state.get("results", []) if r["project"] == project), None
    )
    return NotADCRResponse(
        project=project,
        reason=(result or {}).get("reason") or "No quality issue found.",
        summary=(result or {}).get("summary", ""),
        emails=(result or {}).get("emails", 0),
        pending_drafts=sum(1 for r in store.all() if r.status == "Draft"),
    )


@router.post("/blank/{project}")
def wizard_blank(project: str, entered_by: Optional[str] = None):
    """Create a blank entry for a project with no correspondence."""
    return _blank_entry(project, entered_by)
