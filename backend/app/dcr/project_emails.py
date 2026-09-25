"""E-mails saved per project: resources/<project number>/*.msg|*.eml.

A project folder may sit directly in resources/ or deeper (e.g. resources/SHOWCASE/20241189), and one
folder may cover several numbers ("50137645, 50137647").
"""

import logging
import re
from pathlib import Path

from app.dcr.email_parser import ParsedEmail, parse_any
from app.resources import resource_path

log = logging.getLogger(__name__)

RESOURCES_DIR = resource_path()
EMAIL_SUFFIXES = {".eml", ".msg"}
# runtime folders, plus the synthetic test e-mails (they reuse real project numbers)
SKIP_DIRS = {"data", "output", "master_data", "sample_emails"}
AUTO_REPLY = re.compile(
    r"^\s*(automatic reply|automatische antwort|out of office|abwesenheit|réponse automatique)\b", re.I
)


def _numbers(folder_name: str) -> list[str]:
    return [p for p in re.split(r"[,;\s]+", folder_name) if p]


def _email_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EMAIL_SUFFIXES)


def _candidate_dirs():
    for d in RESOURCES_DIR.rglob("*"):
        if d.is_dir() and d.relative_to(RESOURCES_DIR).parts[0] not in SKIP_DIRS:
            yield d


def find_project_dirs(project: str) -> list[Path]:
    project = project.strip()
    return sorted(d for d in _candidate_dirs() if project in _numbers(d.name) and _email_files(d))


def list_projects() -> list[dict]:
    """Every folder holding e-mails, keyed by the project number(s) in its name."""
    out = []
    for d in _candidate_dirs():
        files = _email_files(d)
        if files:
            out.append({"project": d.name, "folder": d.relative_to(RESOURCES_DIR).as_posix(), "emails": len(files)})
    return sorted(out, key=lambda x: x["project"])


# Parsing .msg files with embedded attachments is slow; reading a project and then saving the entry
# parses the same files twice. Keyed by path, invalidated when the file changes.
_parsed: dict[Path, tuple[float, ParsedEmail]] = {}


def _parse(path: Path) -> ParsedEmail:
    mtime = path.stat().st_mtime
    cached = _parsed.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    email = parse_any(path.read_bytes())
    _parsed[path] = (mtime, email)
    return email


def load_project_emails(project: str) -> tuple[list[ParsedEmail], list[dict]]:
    """All readable e-mails of a project, oldest first, without auto-replies and duplicates.

    Returns (emails, skipped) where skipped explains each file that was left out.
    """
    emails: list[ParsedEmail] = []
    skipped: list[dict] = []
    seen: set[str] = set()
    for folder in find_project_dirs(project):
        for path in _email_files(folder):
            name = path.relative_to(RESOURCES_DIR).as_posix()
            try:
                email = _parse(path)
            except Exception as e:  # e.g. a corrupt .msg
                log.warning("Could not read %s: %s", name, e)
                skipped.append({"file": name, "reason": "unreadable file"})
                continue
            if AUTO_REPLY.match(email.subject):
                skipped.append({"file": name, "reason": "auto-reply"})
                continue
            if email.message_id in seen:
                skipped.append({"file": name, "reason": "duplicate"})
                continue
            seen.add(email.message_id)
            emails.append(email)
    emails.sort(key=lambda e: e.date or "")
    return emails, skipped
