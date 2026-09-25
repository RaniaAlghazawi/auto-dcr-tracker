"""Projects and their email correspondence.

A project number is the organising unit: one folder of correspondence per
project, which may hold several separate email chains because one complaint can
involve a customer, a supplier and a freight forwarder all at once.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.resources import resource_path

PROJECT_NUMBER = re.compile(r"\b(20\d{6})\b")

#: Our own domains, so we never mistake a colleague for the customer.
INTERNAL_DOMAINS = {"amex-healthcare.com", "amexhealthcare.com"}

#: Domains that are infrastructure rather than a trading partner.
NOISE_DOMAINS = {
    # Infrastructure
    "microsoft.com", "hornetsecurity.com", "mimecast.com", "proofpoint.com",
    # Free mail. A supplier contact writing from a personal address must not
    # turn into a company called "AOL" -- their real employer normally appears
    # elsewhere in the same thread.
    "outlook.com", "hotmail.com", "gmail.com", "googlemail.com", "yahoo.com",
    "yahoo.co.uk", "aol.com", "icloud.com", "me.com", "gmx.de", "gmx.net",
    "web.de", "live.com", "msn.com",
}

#: Known partners, so a display name beats a bare domain where we have one.
DOMAIN_NAMES = {
    "randox.com": "Randox Laboratories",
    "pfizer.com": "Pfizer",
    "siemens-healthineers.com": "Siemens Healthineers",
    "siemens.com": "Siemens",
    "who.int": "WHO",
    "undp.org": "UNDP",
    "unicef.org": "UNICEF",
    "ghsc-psm.org": "GHSC-PSM",
    "chemonics.com": "GHSC-PSM (Chemonics)",
    "theglobalfund.org": "Global Fund",
    "kuehne-nagel.com": "Kuehne+Nagel",
    "dhl.com": "DHL Global Forwarding",
    "dsv.com": "DSV",
    "un.org": "United Nations",
    "undp.org": "UNDP",
    "wfp.org": "WFP",
    "ida.org": "IDA Foundation",
}


@dataclass
class ProjectInfo:
    number: str
    directory: Optional[Path]
    email_count: int = 0
    thread_count: int = 0
    first_email: Optional[datetime] = None
    last_email: Optional[datetime] = None
    parties: list[tuple[str, int]] = field(default_factory=list)
    threads: list[str] = field(default_factory=list)
    #: Emails on disk that the time budget did not reach yet.
    pending: int = 0

    @property
    def exists(self) -> bool:
        return self.directory is not None


# ------------------------------------------------------------------ discovery

def projects_root() -> Path:
    return resource_path()


def find_project_dir(project_number: str) -> Optional[Path]:
    """Locate the correspondence folder for a project number."""
    number = (project_number or "").strip()
    if not number:
        return None
    root = projects_root()
    if not root.exists():
        return None

    exact = root / number
    if exact.is_dir():
        return exact
    # Tolerate folders like "20241189 Bleach" or "Project_20241189".
    for candidate in sorted(root.iterdir()):
        if candidate.is_dir() and number in candidate.name:
            return candidate
    return None


def known_projects() -> list[str]:
    root = projects_root()
    if not root.exists():
        return []
    found = []
    for candidate in sorted(root.iterdir()):
        if not candidate.is_dir():
            continue
        # Skip directories that are not project folders
        if candidate.name in {"master_data", "sample_emails", "data", "output", "SHOWCASE", "TEST_NEW_ENTRIES"}:
            continue
        match = PROJECT_NUMBER.search(candidate.name)
        if match:
            found.append(match.group(1))
    return found


# --------------------------------------------------------------------- inference

def _domain_of(address: Optional[str]) -> Optional[str]:
    if not address or "@" not in address:
        return None
    return address.rsplit("@", 1)[-1].strip().lower().strip(">")


#: Second-level suffixes, so "example.co.uk" yields "example", not "example.co".
COMPOUND_TLDS = {"co", "com", "org", "net", "gov", "ac", "or"}


def _display_for(domain: str, fallback_name: Optional[str]) -> str:
    """A readable organisation name from an email domain.

    The sender's personal name is deliberately ignored -- "Chloe McConville"
    does not tell a Quality reviewer which company is involved, the domain does.
    """
    if domain in DOMAIN_NAMES:
        return DOMAIN_NAMES[domain]

    parts = domain.split(".")
    stem = parts[0]
    if len(parts) > 2 and parts[-2] in COMPOUND_TLDS:
        stem = parts[-3]
    elif len(parts) > 1:
        stem = parts[-2]

    stem = stem.replace("-", " ")
    # Short stems are nearly always initialisms: un, who, dsv, ida.
    return stem.upper() if len(stem) <= 4 else stem.title()


def external_parties(emails: list) -> list[tuple[str, int]]:
    """External organisations in the correspondence, most frequent first.

    Counted by sender domain: who actually wrote, not who was copied, which
    keeps distribution lists from outranking the real counterparty.
    """
    from collections import Counter
    counts: Counter[str] = Counter()
    for email in emails:
        domain = _domain_of(getattr(email, "sender", None) or "")
        if not domain or domain in INTERNAL_DOMAINS or domain in NOISE_DOMAINS:
            continue
        counts[_display_for(domain, getattr(email, "sender", None))] += 1
    return counts.most_common()


def summarise(project_number: str) -> ProjectInfo:
    """Everything the wizard shows after a project number is typed."""
    from app.dcr.email_parser import parse_any

    directory = find_project_dir(project_number)
    info = ProjectInfo(number=project_number, directory=directory)
    if directory is None:
        return info

    files = sorted(directory.glob("**/*.msg"))
    emails = []
    for file_path in files:
        try:
            email = parse_any(file_path.read_bytes())
            emails.append(email)
        except Exception:
            continue

    info.email_count = len(emails)
    info.pending = max(0, len(files) - len(emails))

    # Count threads by subject
    from collections import Counter
    threads: Counter[str] = Counter()
    for email in emails:
        subject = getattr(email, "subject", "") or ""
        if subject:
            threads[subject] += 1

    info.thread_count = len(threads)
    info.threads = [subject for subject, _ in threads.most_common(10)]

    dates = [getattr(e, "date", None) for e in emails if getattr(e, "date", None)]
    if dates:
        info.first_email = min(dates)
        info.last_email = max(dates)

    info.parties = external_parties(emails)
    return info
