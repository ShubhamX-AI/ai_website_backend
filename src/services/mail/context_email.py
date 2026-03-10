import asyncio
import html
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from string import Template

from pydantic import BaseModel

from src.core.config import settings
from src.services._ai_formatter import llm_parse

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "context_email.html"
_EMAIL_TEMPLATE: Template | None = None

_SYSTEM_PROMPT = (
    "You format concise business emails from UI snapshot data. "
    "Rules: factual, no filler phrases, no greetings, no questions, "
    "no markdown, 3–5 bullet points each under 140 characters, "
    "subject prefixed with 'Indus Net | ', heading must be specific "
    "and descriptive (never generic like 'Summary' or 'Details')."
)


class EmailSchema(BaseModel):
    subject: str        # e.g. "Indus Net | Global Office Locations"
    heading: str        # e.g. "Global Office Locations"
    context_line: str   # one sentence, no filler
    bullet_points: list[str]  # 3–5 items, each under 140 chars


def is_valid_email_address(email: str) -> bool:
    return bool(email and _EMAIL_RE.match(email.strip()))


def _load_email_template() -> Template:
    global _EMAIL_TEMPLATE
    if _EMAIL_TEMPLATE is None:
        with _TEMPLATE_PATH.open("r", encoding="utf-8") as f:
            _EMAIL_TEMPLATE = Template(f.read())
    return _EMAIL_TEMPLATE


async def compose_context_email(
    snapshot: dict, user_name: str | None = None
) -> tuple[str, str, str]:
    """Compose subject, plain text, and HTML from a UI snapshot using LLM."""

    greeting = f"Hi {user_name.strip()}," if user_name and user_name.strip() else "Hi there,"

    pres = await llm_parse(snapshot, _SYSTEM_PROMPT, EmailSchema) or _fallback_format(snapshot)

    # Plain text
    plain_bullets = "\n".join(f"- {p}" for p in pres.bullet_points)
    plain_body = (
        f"{pres.heading}\n\n{greeting}\n\n"
        f"{pres.context_line}\n\nKey Points:\n{plain_bullets}\n\nIndus Net Assistant\n"
    )

    # HTML
    bullet_html = "".join(
        f'<li style="margin: 0 0 10px;">{html.escape(p)}</li>'
        for p in pres.bullet_points
    )
    html_body = _load_email_template().safe_substitute(
        escaped_subject=html.escape(pres.subject),
        escaped_heading=html.escape(pres.heading),
        escaped_greeting=html.escape(greeting),
        escaped_context_line=html.escape(pres.context_line),
        bullet_points_html=bullet_html,
    )

    return pres.subject, plain_body, html_body


def _fallback_format(snapshot: dict) -> EmailSchema:
    """Minimal fallback when LLM is unavailable."""
    title = str(snapshot.get("title") or snapshot.get("type") or "Requested Information")
    summary = str(snapshot.get("summary") or "")
    return EmailSchema(
        subject=f"Indus Net | {title}"[:140],
        heading=title[:80],
        context_line="Key information shared by Indus Net Assistant.",
        bullet_points=[summary[:140]] if summary else ["Details available from Indus Net Assistant."],
    )


def _smtp_send(msg: MIMEMultipart, sender_email: str, sender_password: str, recipient_email: str) -> None:
    """Blocking SMTP call — always run via asyncio.to_thread."""
    server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, [recipient_email], msg.as_string())
    server.quit()


async def send_context_email(
    recipient_email: str,
    snapshot: dict,
    user_name: str | None = None,
    sender_email: str | None = None,
    sender_password: str | None = None,
) -> tuple[bool, str]:
    sender_email = sender_email or settings.SENDER_EMAIL
    sender_password = sender_password or settings.SENDER_PASSWORD

    if not sender_email or not sender_password:
        return False, "Email sender credentials are not configured."
    if not is_valid_email_address(recipient_email):
        return False, "Recipient email address is invalid."

    try:
        subject, plain_text, html_body = await compose_context_email(snapshot, user_name)
    except Exception as exc:
        logger.error("Failed to compose email: %s", exc)
        return False, f"Failed to compose email: {exc}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await asyncio.to_thread(_smtp_send, msg, sender_email, sender_password, recipient_email)
        logger.info("Context email sent to %s", recipient_email)
        return True, "Context email sent successfully."
    except Exception as exc:
        logger.error("SMTP error: %s", exc)
        return False, "Failed to send context email due to SMTP error."