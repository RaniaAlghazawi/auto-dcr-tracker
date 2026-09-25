"""DCR record model — mirrors the columns of the SOP 5-A1 "DCR Tracker and CAPA Overview".

Drop-down values come from the tracker's "Formulas" sheet; field meanings come from its
"Instructions and definitions" sheet.
"""

from typing import Literal

from pydantic import BaseModel, Field

DCR_TYPES = ["Deviation", "Complaint", "Recall", "Safety notice", "Partner issue report"]
RESPONSIBLE_PARTIES = ["AMEX", "Customer", "Freight forwarder", "Supplier", "Warehouse"]
CATEGORIES = [
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
OFFICES = ["Vienna", "Kenya"]

Status = Literal["Draft", "Open", "Closed"]
Source = Literal["tracker", "email"]


class SourceEmail(BaseModel):
    message_id: str
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    sender: str
    subject: str
    date: str | None = None
    body: str
    attachments: list[str] = Field(default_factory=list)


class DCR(BaseModel):
    id: str = Field(description="Internal id (stable, never shown as the tracking number).")
    tracking_number: str | None = Field(None, description="YY-NNN, assigned when a draft is confirmed.")
    type: str | None = None
    critical: str | None = None  # Y / N / N/A
    occurred_on: str | None = None  # ISO date
    entered_by: str | None = None
    amex_office: str | None = None
    pharma: str | None = None  # Y / N
    supplier: str | None = None
    customer: str | None = None
    project: str | None = None
    responsible_party: str | None = None
    responsible_party_name: str | None = None
    category: str | None = None
    description: str | None = None
    root_cause: str | None = None
    financial_impact: str | None = None
    actions_taken: str | None = None
    capa_needed: str | None = None  # Y / N
    capa_plan: str | None = None
    actions: str | None = None
    closure_date: str | None = None  # ISO date, or free text if the tracker had text

    # App-level fields (not tracker columns)
    excel_row: int | None = Field(None, description="Row in the tracker workbook's Main Sheet.")
    status: Status = "Open"
    source: Source = "tracker"
    freight_forwarder: str | None = None
    reported_by_party: str | None = Field(None, description="Who raised it: Customer / Supplier / Freight forwarder / ...")
    source_emails: list[SourceEmail] = Field(default_factory=list)
    requested_actions: str | None = Field(None, description="What the e-mail sender asks AMEX to do.")
    extraction_method: str | None = None  # "claude" | "rules"
    issues: list[str] = Field(default_factory=list, description="Data-quality findings, see quality.py")


class DCRUpdate(BaseModel):
    """Editable fields for PATCH — everything a QA reviewer may correct."""

    type: str | None = None
    critical: str | None = None
    occurred_on: str | None = None
    entered_by: str | None = None
    amex_office: str | None = None
    pharma: str | None = None
    supplier: str | None = None
    customer: str | None = None
    project: str | None = None
    responsible_party: str | None = None
    responsible_party_name: str | None = None
    category: str | None = None
    description: str | None = None
    root_cause: str | None = None
    financial_impact: str | None = None
    actions_taken: str | None = None
    capa_needed: str | None = None
    capa_plan: str | None = None
    actions: str | None = None
    closure_date: str | None = None
    freight_forwarder: str | None = None
