import datetime as dt
import html
import logging
import re
import smtplib
import os
from string import Template
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.core.config import settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


def is_valid_email_address(email: str) -> bool:
    """Return True when email is syntactically valid for operational use."""
    if not email:
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def _build_subject(snapshot: dict) -> str:
    title = (snapshot or {}).get("title") or "Indus Net Summary"
    return f"Requested details: {title}"[:140]


def _to_bullets(details: dict) -> list[str]:
    lines: list[str] = []
    for key, value in (details or {}).items():
        key_text = str(key).replace("_", " ").strip().title()
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"- {key_text}: {', '.join(str(v) for v in value)}")
            continue
        if isinstance(value, dict):
            if not value:
                continue
            compact = ", ".join(f"{k}: {v}" for k, v in value.items())
            lines.append(f"- {key_text}: {compact}")
            continue
        if value is None or value == "":
            continue
        lines.append(f"- {key_text}: {value}")
    return lines


def compose_context_email(snapshot: dict, user_name: str | None = None) -> tuple[str, str, str]:
    """Compose deterministic subject/plain/html content from the last shown UI snapshot."""
    snap = snapshot or {}
    title = snap.get("title", "Details")
    summary = snap.get("summary", "")
    details = snap.get("details", {})
    source_tool = snap.get("source_tool", "")
    timestamp = snap.get("timestamp", "")

    greeting_name = user_name or "there"
    subject = _build_subject(snap)

    detail_lines = _to_bullets(details)
    details_text = "\n".join(detail_lines) if detail_lines else "- No extra details were available."

    plain_text = (
        f"Hi {greeting_name},\n\n"
        "Here is the summary you requested from your recent assistant session.\n\n"
        f"Title: {title}\n"
        f"Summary: {summary or 'No summary available.'}\n\n"
        "Details:\n"
        f"{details_text}\n\n"
        "Context metadata:\n"
        f"- Source tool: {source_tool or 'unknown'}\n"
        f"- Generated at: {timestamp or dt.datetime.now(dt.timezone.utc).isoformat()}\n\n"
        "Best regards,\n"
        "Indus Net Assistant\n"
    )

    escaped_title = html.escape(str(title))
    escaped_summary = html.escape(str(summary or "No summary available."))
    escaped_source = html.escape(str(source_tool or "unknown"))
    escaped_time = html.escape(str(timestamp or dt.datetime.now(dt.timezone.utc).isoformat()))
    details_html = "".join(f"<li>{html.escape(line[2:])}</li>" for line in detail_lines)
    if not details_html:
        details_html = "<li>No extra details were available.</li>"

    template_path = os.path.join(os.path.dirname(__file__), "templates", "context_email.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = Template(f.read())

    html_body = html_template.safe_substitute(
        greeting_name=html.escape(str(greeting_name)),
        escaped_title=escaped_title,
        escaped_summary=escaped_summary,
        details_html=details_html,
        escaped_source=escaped_source,
        escaped_time=escaped_time
    )

    return subject, plain_text, html_body


def send_context_email(
    recipient_email: str,
    snapshot: dict,
    user_name: str | None = None,
    sender_email: str | None = None,
    sender_password: str | None = None,
) -> tuple[bool, str]:
    """Send contextual summary email with text and HTML parts."""
    sender_email = sender_email or settings.SENDER_EMAIL
    sender_password = sender_password or settings.SENDER_PASSWORD

    if not sender_email or not sender_password:
        logger.error("Sender email credentials are not configured")
        return False, "Email sender credentials are not configured."

    if not is_valid_email_address(recipient_email):
        return False, "Recipient email address is invalid."

    subject, plain_text, html_body = compose_context_email(snapshot, user_name=user_name)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        server.quit()
        logger.info("Context email sent to %s", recipient_email)
        return True, "Context email sent successfully."
    except Exception as exc:
        logger.error("Failed to send context email: %s", exc)
        return False, "Failed to send context email due to SMTP error."
