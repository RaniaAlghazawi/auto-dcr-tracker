"""Parse e-mails (.eml / pasted text / Outlook .msg) into a simple structure."""

import hashlib
import io
import re
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime

from pydantic import BaseModel, Field

NO_SUBJECT = "(no subject)"
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # Outlook .msg files are OLE compound documents
SUBJECT_PREFIX = re.compile(r"^\s*((re|fw|fwd|aw|wg|antw|tr)\s*:\s*|\[ext\]\s*)+", re.I)


class ParsedEmail(BaseModel):
    message_id: str
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    sender: str
    sender_domain: str | None = None
    to: str | None = None
    cc: str | None = None
    subject: str
    date: str | None = None  # ISO datetime
    body: str
    attachments: list[str] = Field(default_factory=list)

    @property
    def thread_subject(self) -> str:
        return normalize_subject(self.subject)


def normalize_subject(subject: str) -> str:
    return re.sub(r"\s+", " ", SUBJECT_PREFIX.sub("", subject or "")).strip().lower()


def domain_of(sender: str) -> str | None:
    m = re.search(r"@([\w.-]+)", sender or "")
    return m.group(1).lower() if m else None


def _fallback_id(data: bytes) -> str:
    return "<generated-" + hashlib.sha1(data).hexdigest()[:16] + ">"


def _ids(value) -> list[str]:
    return re.findall(r"<[^>]+>", str(value or ""))


def parse_email(raw: str | bytes) -> ParsedEmail:
    # Parse bytes, not str: with a str source the email package mangles 8-bit UTF-8 bodies (° → �).
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    msg = BytesParser(policy=policy.default).parsebytes(data)
    has_headers = bool(msg["From"] or msg["Subject"])

    attachments: list[str] = []
    if msg.is_multipart():
        part = msg.get_body(preferencelist=("plain", "html"))
        body = part.get_content() if part else ""
        attachments = [a.get_filename() for a in msg.iter_attachments() if a.get_filename()]
    else:
        body = msg.get_content() if has_headers else data.decode("utf-8", errors="replace")
    if "<html" in body[:500].lower():
        body = re.sub(r"<[^>]+>", " ", body)

    date_iso = None
    if msg["Date"]:
        try:
            date_iso = parsedate_to_datetime(str(msg["Date"])).isoformat()
        except (TypeError, ValueError):
            pass

    sender = str(msg["From"] or "unknown")
    return ParsedEmail(
        message_id=str(msg["Message-ID"] or "").strip() or _fallback_id(data),
        in_reply_to=str(msg["In-Reply-To"]).strip() if msg["In-Reply-To"] else None,
        references=_ids(msg["References"]),
        sender=sender,
        sender_domain=domain_of(sender),
        to=str(msg["To"]) if msg["To"] else None,
        cc=str(msg["Cc"]) if msg["Cc"] else None,
        subject=str(msg["Subject"] or NO_SUBJECT),
        date=date_iso,
        body=body.strip(),
        attachments=attachments,
    )


def parse_msg(data: bytes) -> ParsedEmail:
    import extract_msg

    m = extract_msg.Message(io.BytesIO(data))
    try:
        sender = str(m.sender or "unknown")
        date = m.date.isoformat() if getattr(m, "date", None) else None
        body = (m.body or "").replace("\r\n", "\n")
        # strip the long tracking links security gateways add to every URL
        body = re.sub(r"<https?://[^>\s]{120,}>", "", body)
        header = getattr(m, "header", None)
        in_reply_to = header.get("In-Reply-To") if header else None
        return ParsedEmail(
            message_id=(getattr(m, "messageId", None) or "").strip() or _fallback_id(data),
            in_reply_to=in_reply_to.strip() if in_reply_to else None,
            references=_ids(header.get("References")) if header else [],
            sender=sender,
            sender_domain=domain_of(sender),
            to=m.to,
            cc=m.cc,
            subject=m.subject or NO_SUBJECT,
            date=date,
            body=re.sub(r"\n\s*\n\s*\n+", "\n\n", body).strip(),
            attachments=[a.longFilename for a in m.attachments if getattr(a, "longFilename", None)],
        )
    finally:
        m.close()


def parse_any(data: bytes) -> ParsedEmail:
    """.msg (Outlook) or RFC 822 text (.eml / .txt)."""
    if data[:8] == OLE_SIGNATURE:
        return parse_msg(data)
    return parse_email(data)
