"""Data-quality checks derived from the tracker's "Instructions and definitions" sheet."""

import re
from datetime import date

from app.dcr.normalize import is_blank, parse_iso
from app.dcr.schema import CATEGORIES, DCR, DCR_TYPES, OFFICES, RESPONSIBLE_PARTIES

REQUIRED = {
    "type": "Type",
    "occurred_on": "DCR occurred on",
    "entered_by": "Entered by",
    "amex_office": "AMEX office",
    "pharma": "Pharma (Y/N)",
    "customer": "Customer",
    "project": "Project",
    "responsible_party": "Responsible party",
    "category": "Category",
    "description": "Description",
}
OPEN_TOO_LONG_DAYS = 60
MIN_DESCRIPTION_CHARS = 40
# "Critical DCR (Y/N)" was added to the tracker with SOP 5-A1 v4; earlier cases carry N/A.
CRITICAL_FIELD_SINCE = "26-064"


def check(dcr: DCR, today: date | None = None) -> list[str]:
    today = today or date.today()
    issues: list[str] = []

    for field, label in REQUIRED.items():
        if getattr(dcr, field) is None:
            issues.append(f"Missing: {label}")

    if dcr.type and dcr.type not in DCR_TYPES:
        issues.append(f"Type '{dcr.type}' is not in the drop-down list")
    if dcr.category and dcr.category not in CATEGORIES:
        issues.append(f"Category '{dcr.category}' is not in the drop-down list")
    if dcr.responsible_party and dcr.responsible_party not in RESPONSIBLE_PARTIES:
        issues.append(f"Responsible party '{dcr.responsible_party}' is not in the drop-down list")
    if dcr.amex_office and dcr.amex_office not in OFFICES:
        issues.append(f"AMEX office '{dcr.amex_office}' is not Vienna/Kenya")
    if dcr.category == "Other":
        issues.append("Category 'Other' — check whether a specific category fits")

    tracked_since_v4 = not dcr.tracking_number or dcr.tracking_number >= CRITICAL_FIELD_SINCE
    if dcr.critical not in ("Y", "N") and tracked_since_v4:
        issues.append("Critical DCR not assessed (Y/N)")

    occurred = parse_iso(dcr.occurred_on)
    if dcr.occurred_on and not occurred:
        issues.append(f"Occurred date '{dcr.occurred_on}' is not a valid date")

    desc = dcr.description or ""
    if desc and len(desc) < MIN_DESCRIPTION_CHARS:
        issues.append("Description too short to explain what happened")

    if dcr.status != "Draft":
        if is_blank(dcr.root_cause):
            issues.append("Root cause missing")
        elif desc and dcr.root_cause.strip().lower() == desc.strip().lower():
            issues.append("Root cause repeats the description (should explain how/why)")
        if dcr.capa_needed not in ("Y", "N"):
            issues.append("CAPA report needed (Y/N) not set")
        if dcr.capa_needed == "Y" and is_blank(dcr.capa_plan):
            issues.append("CAPA needed but no CAPA plan")
        if is_blank(dcr.actions_taken) and is_blank(dcr.capa_plan):
            issues.append("No actions taken or CAPA plan recorded")

    if dcr.financial_impact and not is_blank(dcr.financial_impact):
        if not re.fullmatch(r"[\d.,\s]+(€|eur|usd|\$)?", dcr.financial_impact.strip().lower()):
            issues.append("Financial impact is not a plain amount")

    closure = parse_iso(dcr.closure_date)
    if dcr.closure_date and not closure and dcr.closure_date.lower() != "closed":
        issues.append("Closure date is free text, not a date")
    if closure and occurred and closure < occurred:
        issues.append("Closure date is before the occurred date")
    if dcr.status == "Open" and occurred and (today - occurred).days > OPEN_TOO_LONG_DAYS:
        issues.append(f"Open for more than {OPEN_TOO_LONG_DAYS} days")

    return issues
