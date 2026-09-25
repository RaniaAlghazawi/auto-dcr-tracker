"""Turn an e-mail thread into a DCR tracker entry.

Two strategies:
- "claude": Claude reads the thread with the SOP 5-A1 field definitions and returns structured fields.
- "rules":  keyword/regex heuristics, used when no ANTHROPIC_API_KEY is configured or Claude fails.
"""

import logging
import os
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.dcr.email_parser import ParsedEmail
from app.dcr.master_data import MasterData
from app.dcr.schema import CATEGORIES, DCR_TYPES, RESPONSIBLE_PARTIES

log = logging.getLogger(__name__)

CLAUDE_MODEL = os.getenv("DCR_CLAUDE_MODEL", "claude-opus-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

DcrType = Literal["Deviation", "Complaint", "Recall", "Safety notice", "Partner issue report"]
Category = Literal[
    "Damaged item",
    "Delayed shipment",
    "Missing item",
    "Other",
    "Product quality issue",
    "Temperature excursion",
    "Wrong item",
    "Wrong quotation",
    "Adverse event",
    "Partner issue report",
]
Responsible = Literal["AMEX", "Customer", "Freight forwarder", "Supplier", "Warehouse"]
Office = Literal["Vienna", "Kenya"]
YN = Literal["Y", "N"]


class Extraction(BaseModel):
    is_dcr: bool = Field(
        description="True if the thread reports a deviation, complaint, recall, safety notice or partner issue."
    )
    title: str = Field(description="Short headline, max 80 characters.")
    type: DcrType | None = None
    category: Category | None = None
    critical: YN | None = Field(None, description="Y only for a clear patient-safety / product-integrity risk.")
    occurred_on: str | None = Field(None, description="ISO date the issue occurred; else the date AMEX became aware.")
    amex_office: Office | None = Field(None, description="AMEX office impacted: Vienna or Kenya.")
    pharma: YN | None = Field(None, description="Y if a pharmaceutical product/shipment is involved.")
    supplier: str | None = Field(None, description="Supplier / manufacturer company name.")
    customer: str | None = Field(None, description="Customer organisation name only, not the end destination.")
    project: str | None = Field(None, description="AMEX project number, e.g. 20231687 or 20231789-1.")
    freight_forwarder: str | None = None
    reported_by_party: Responsible | None = Field(None, description="Which kind of party raised the issue.")
    responsible_party: Responsible | None = Field(None, description="Who caused the issue, if the e-mails indicate it.")
    responsible_party_name: str | None = Field(None, description="Company name of the responsible party.")
    description: str = Field(
        description="What happened, chronologically, WHAT not WHY. Include items, lot/batch, quantities, refs."
    )
    root_cause: str | None = Field(None, description="Only if the e-mails state how/why it happened.")
    financial_impact: str | None = Field(None, description="Amount with currency, only if stated (e.g. '8177 EUR').")
    actions_taken: str | None = Field(None, description="Actions already taken or agreed in the thread.")
    capa_needed: YN | None = Field(None, description="Y if the thread asks for a CAPA / investigation report.")
    closure_date: str | None = Field(None, description="ISO date, only if the thread states the case is closed.")
    requested_actions: str | None = Field(None, description="What the sender asks AMEX to do.")
    missing_information: list[str] = Field(default_factory=list, description="Tracker fields the e-mails do not answer.")


SYSTEM_PROMPT = f"""You are the Quality assistant at AMEX Healthcare (medical supplies and pharmaceuticals for
humanitarian customers; offices in Vienna and Kenya). You read e-mail threads from customers, suppliers,
freight forwarders and warehouses and fill one row of the DCR tracker (SOP 5-A1 "DCR Tracker and CAPA
Overview"). A QA reviewer checks your row, so never invent facts: leave a field null when the e-mails do
not support it and list it under missing_information.

Tracker rules (from the SOP 5-A1 instructions):
- Type is one of {DCR_TYPES}.
  Deviation = departure from an approved process/spec noticed by AMEX or a partner (temperature excursion,
  delay, documentation gaps, GDP issues). Complaint = a customer or end user reports dissatisfaction with
  delivered goods or service. Recall = a manufacturer withdraws product. Safety notice = field safety
  notice / important product information without withdrawal. Partner issue report = issue about a partner.
- Category is one of {CATEGORIES}. Use "Other" only when nothing else fits.
- Responsible party is one of {RESPONSIBLE_PARTIES} — who caused the issue, not who reported it.
- Customer = customer organisation only, not the end destination (put the destination in the description).
- Description explains WHAT happened chronologically, not HOW/WHY. Root cause (how/why) is separate.
- Critical = Y only for a clear patient-safety or product-integrity risk (recall of affected lots in the
  field, sterility breach, cold-chain excursion without stability data); otherwise N; null if unclear.
- CAPA needed = Y when the customer requests a CAPA / deviation / investigation report or the issue is
  recurring; N when simple corrective actions close it; null if unclear.
- Dates: ISO format (YYYY-MM-DD).
Threads usually quote earlier messages below the newest one — read all of it. Ignore signatures,
disclaimers and security-gateway links. Auto-replies, order confirmations, quotes and pure logistics
coordination without a problem are not DCRs (is_dcr = false)."""


def thread_text(emails: list[ParsedEmail]) -> str:
    parts = []
    for i, e in enumerate(emails, 1):
        att = f"\nAttachments: {', '.join(e.attachments)}" if e.attachments else ""
        parts.append(f"--- E-mail {i} ---\nFrom: {e.sender}\nDate: {e.date}\nSubject: {e.subject}{att}\n\n{e.body}")
    return "\n\n".join(parts)


def _master_data_hint(emails: list[ParsedEmail], master: MasterData) -> str:
    lines = []
    for e in emails:
        party = master.party_for_domain(e.sender_domain)
        if party:
            lines.append(f"Sender {e.sender} is a known {party.type}: {party.name}")
    for number in sorted({p for e in emails for p in find_projects(e.subject + " " + e.body)}):
        project = master.project(number)
        if project:
            lines.append(f"Project {number} in the tracker history: {project.model_dump(exclude_none=True)}")
    return "\n".join(dict.fromkeys(lines)) or "(no master-data matches)"


def extract_with_claude(emails: list[ParsedEmail], master: MasterData) -> Extraction | None:
    import anthropic

    client = anthropic.Anthropic()
    request = dict(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Today is {date.today().isoformat()}.\n\nKnown master data:\n{_master_data_hint(emails, master)}"
                f"\n\nE-mail thread:\n\n{thread_text(emails)}",
            }
        ],
        output_format=Extraction,
    )
    try:
        # Server-side fallback re-runs a request declined by a safety classifier on another model.
        response = client.beta.messages.parse(**request, betas=[FALLBACK_BETA], fallbacks="default")
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e).lower():
            raise
        log.warning("Server-side fallbacks unavailable for this account; retrying without them")
        response = client.messages.parse(**request)
    if response.stop_reason == "refusal":
        log.warning("Claude declined the extraction; falling back to rules")
        return None
    return response.parsed_output


# ---------------------------------------------------------------- rules fallback

PROJECT_RE = re.compile(r"\b(20\d{6}(?:-\d{1,2})?)\b")

CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Temperature excursion", ["temperature excursion", "data logger", "datalogger", "cold chain", "excursion", "temperaturabweichung"]),
    ("Damaged item", ["damaged", "crushed", "broken", "torn", "dented", "leaking", "beschädigt"]),
    ("Missing item", ["short delivery", "missing", "but only", "not delivered", "shortage", "fehlt"]),
    ("Wrong item", ["wrong item", "wrong product", "incorrect item"]),
    ("Wrong quotation", ["quotation", "quoted", "price difference"]),
    ("Product quality issue", ["recall", "calibration", "defect", "out of specification", "certificate of analysis", "expiry date", "labelling", "field safety"]),
    ("Delayed shipment", ["delay", "late delivery", "held at", "customs", "postponed"]),
]

DCR_SIGNALS = [
    "complaint", "deviation", "recall", "field safety", "safety notice", "excursion", "damaged", "missing",
    "short delivery", "delay", "defect", "wrong", "broken", "crushed", "incident", "pqi", "beschädigt", "abweichung",
]
NOT_DCR_SUBJECTS = ["automatic reply", "out of office", "abwesenheit", "order confirmation", "auftragsbestätigung"]
CUSTOMER_COMPLAINT_WORDS = ["we received", "we ordered", "replacement", "credit note", "arrived", "incident was reported"]


def find_projects(text: str) -> list[str]:
    return list(dict.fromkeys(PROJECT_RE.findall(text)))


def _newest_part(body: str) -> str:
    """The newest message only — cut the quoted history below it."""
    return re.split(r"\n(?:From|Von|От|De):\s", body, maxsplit=1)[0]


def _description(emails: list[ParsedEmail]) -> str:
    chunks = []
    for e in emails:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", _newest_part(e.body)) if p.strip()]
        core = [
            p for p in paragraphs
            if not re.match(r"^(dear|hello|hi|good (morning|afternoon)|kind regards|best regards|regards|sincerely|many thanks|sehr geehrte|liebe|mit freundlichen)\b", p, re.I)
            and len(p) > 30
        ]
        text = " ".join(" ".join(core).split())
        if text:
            prefix = f"[{(e.date or '')[:10]}] " if len(emails) > 1 else ""
            chunks.append(prefix + text[:700])
    return "\n".join(chunks)


def extract_with_rules(emails: list[ParsedEmail], master: MasterData) -> Extraction:
    first = emails[0]
    text = " ".join(f"{e.subject}\n{e.body}" for e in emails)
    low = text.lower()

    is_dcr = any(s in low for s in DCR_SIGNALS) and not any(s in first.subject.lower() for s in NOT_DCR_SUBJECTS)
    external = [p for p in (master.party_for_domain(e.sender_domain) for e in emails) if p and p.type != "AMEX"]
    sender_party = external[0] if external else None
    reported_by = sender_party.type if sender_party and sender_party.type in RESPONSIBLE_PARTIES else None

    if "field safety" in low or "safety notice" in low or "important product information" in low:
        dcr_type = "Recall" if "recall" in low else "Safety notice"
    elif "recall" in low:
        dcr_type = "Recall"
    elif "complaint" in low or "pqi" in low or reported_by == "Customer" or (
        reported_by is None and any(w in low for w in CUSTOMER_COMPLAINT_WORDS)
    ):
        dcr_type = "Complaint"
    else:
        dcr_type = "Deviation"

    category = next((cat for cat, words in CATEGORY_KEYWORDS if any(w in low for w in words)), "Other")

    projects = find_projects(text)
    project_number = projects[0] if projects else None
    project = master.project(project_number)

    responsible = None
    if dcr_type in ("Recall", "Safety notice") or category == "Product quality issue":
        responsible = "Supplier"
    elif "forwarder" in low or "truck" in low:
        responsible = "Freight forwarder"
    elif reported_by in ("Warehouse", "Supplier", "Freight forwarder"):
        responsible = reported_by

    ex = Extraction(
        is_dcr=is_dcr,
        title=re.sub(r"^\s*((re|fw|fwd|aw|wg)\s*:\s*)+", "", first.subject, flags=re.I)[:80],
        type=dcr_type if is_dcr else None,
        category=category if is_dcr else None,
        critical="Y" if dcr_type == "Recall" else None,
        # SOP: if the occurrence date is unknown, use the date AMEX became aware of it
        occurred_on=(first.date or "")[:10] or date.today().isoformat(),
        amex_office=(project.office if project else None) or ("Kenya" if "kenya" in low or "nairobi" in low else "Vienna"),
        pharma=project.pharma if project else None,
        supplier=(project.supplier if project else None) or (sender_party.name if reported_by == "Supplier" else None),
        customer=(project.customer if project else None) or (sender_party.name if reported_by == "Customer" else None),
        project=project_number,
        freight_forwarder=sender_party.name if reported_by == "Freight forwarder" else None,
        reported_by_party=reported_by,
        responsible_party=responsible,
        responsible_party_name=sender_party.name if sender_party and responsible == sender_party.type else None,
        description=_description(emails),
    )
    ex.missing_information = [
        label for label, value in [
            ("Project", ex.project), ("Customer", ex.customer), ("Supplier", ex.supplier),
            ("Responsible party", ex.responsible_party), ("Pharma (Y/N)", ex.pharma),
            ("Critical DCR (Y/N)", ex.critical), ("Root cause", ex.root_cause),
        ] if not value
    ]
    return ex


def use_claude() -> bool:
    mode = os.getenv("DCR_EXTRACTOR", "auto").lower()
    if mode == "rules":
        return False
    return mode == "claude" or bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def extract(emails: list[ParsedEmail], master: MasterData) -> tuple[Extraction, str]:
    """Returns the extraction and the method that produced it ("claude" or "rules")."""
    if use_claude():
        try:
            result = extract_with_claude(emails, master)
            if result is not None:
                return result, "claude"
        except Exception:  # network, auth, rate limit — keep the tracker usable
            log.exception("Claude extraction failed; falling back to rules")
    return extract_with_rules(emails, master), "rules"
