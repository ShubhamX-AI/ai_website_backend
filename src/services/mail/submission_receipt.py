import datetime as dt
import html
import uuid
from dataclasses import dataclass
from pathlib import Path
from string import Template

from src.services.mail.context_email import send_email_message


@dataclass(frozen=True)
class SubmissionReceiptResult:
    sent: bool
    message: str
    reference_id: str
    submitted_at: str


_RECEIPT_CONFIG = {
    "contact_form": {
        "reference_prefix": "CNT",
        "subject": "Indus Net | Contact Request Receipt",
        "heading": "Your contact request receipt",
        "intro": "This email includes a copy of the contact details captured during your session.",
        "detail_label": "Reason for reaching out",
        "next_steps": [
            "Keep this reference ID if you need to follow up on the same request.",
            "We recommend keeping this email for your records.",
        ],
    },
    "job_application": {
        "reference_prefix": "JOB",
        "subject": "Indus Net | Job Application Receipt",
        "heading": "Your job application receipt",
        "intro": "This email includes a copy of the job application details captured during your session.",
        "detail_label": "Role or opportunity",
        "next_steps": [
            "Keep this reference ID if you want to follow up on this application.",
            "We recommend keeping this email with the details you submitted.",
        ],
    },
}

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "submission_receipt.html"
_RECEIPT_TEMPLATE: Template | None = None


def _build_reference_id(prefix: str, submitted_at: dt.datetime) -> str:
    timestamp = submitted_at.strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{timestamp}-{suffix}"


def _format_submitted_at(submitted_at: dt.datetime) -> str:
    return submitted_at.strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_receipt_template() -> Template:
    global _RECEIPT_TEMPLATE
    if _RECEIPT_TEMPLATE is None:
        with _TEMPLATE_PATH.open("r", encoding="utf-8") as template_file:
            _RECEIPT_TEMPLATE = Template(template_file.read())
    return _RECEIPT_TEMPLATE


def _build_details_rows(details: list[tuple[str, str]]) -> str:
    rows = []
    for label, value in details:
        rows.append(
            "<tr>"
            f'<td style="padding: 13px 14px; border-top: 1px solid #e2e8f0; width: 180px; '
            f'font-weight: 700; vertical-align: top; color: #52637c;">{html.escape(label)}</td>'
            f'<td style="padding: 13px 14px; border-top: 1px solid #e2e8f0; vertical-align: top; color: #0f172a;">{html.escape(value)}</td>'
            "</tr>"
        )
    return "".join(rows)


def _build_next_steps_html(next_steps: list[str]) -> str:
    items = []
    for step in next_steps:
        items.append(f'<li style="margin: 0 0 10px;">{html.escape(step)}</li>')
    return "".join(items)


def _compose_submission_receipt(
    submission_type: str,
    user_name: str,
    user_email: str,
    user_phone: str,
    detail_value: str,
    submitted_at: dt.datetime,
) -> tuple[str, str, str, str, str]:
    if submission_type not in _RECEIPT_CONFIG:
        raise ValueError(f"Unsupported submission type: {submission_type}")

    config = _RECEIPT_CONFIG[submission_type]
    reference_id = _build_reference_id(config["reference_prefix"], submitted_at)
    submitted_at_text = _format_submitted_at(submitted_at)
    cleaned_name = user_name.strip()
    greeting_name = cleaned_name or "there"
    cleaned_detail_value = detail_value.strip() or "Not provided"

    details = [
        ("Reference ID", reference_id),
        ("Submitted at", submitted_at_text),
        ("Status", "Received"),
        ("Name", cleaned_name or "Not provided"),
        ("Email", user_email.strip()),
        ("Phone", user_phone.strip() or "Not provided"),
        (config["detail_label"], cleaned_detail_value),
    ]

    plain_lines = [
        config["heading"],
        "",
        f"Hi {greeting_name},",
        "",
        config["intro"],
        "",
        "Submission details:",
    ]
    plain_lines.extend(f"- {label}: {value}" for label, value in details)
    plain_lines.extend(["", "Next steps:"])
    plain_lines.extend(f"- {step}" for step in config["next_steps"])
    plain_lines.extend(["", "Indus Net Assistant"])
    plain_text = "\n".join(plain_lines)

    html_body = _load_receipt_template().safe_substitute(
        escaped_subject=html.escape(config["subject"]),
        escaped_status=html.escape("Received"),
        escaped_heading=html.escape(config["heading"]),
        escaped_intro=html.escape(config["intro"]),
        escaped_reference_id=html.escape(reference_id),
        escaped_submitted_at=html.escape(submitted_at_text),
        escaped_greeting=html.escape(f"Hi {greeting_name},"),
        details_rows_html=_build_details_rows(details),
        next_steps_html=_build_next_steps_html(config["next_steps"]),
    )

    return (
        config["subject"],
        plain_text,
        html_body,
        reference_id,
        submitted_at_text,
    )


async def send_submission_receipt(
    recipient_email: str,
    submission_type: str,
    user_name: str,
    user_phone: str,
    detail_value: str,
) -> SubmissionReceiptResult:
    submitted_at = dt.datetime.now(dt.timezone.utc)
    subject, plain_text, html_body, reference_id, submitted_at_text = (
        _compose_submission_receipt(
            submission_type=submission_type,
            user_name=user_name,
            user_email=recipient_email,
            user_phone=user_phone,
            detail_value=detail_value,
            submitted_at=submitted_at,
        )
    )

    sent, message = await send_email_message(
        recipient_email=recipient_email,
        subject=subject,
        plain_text=plain_text,
        html_body=html_body,
    )
    return SubmissionReceiptResult(
        sent=sent,
        message=message,
        reference_id=reference_id,
        submitted_at=submitted_at_text,
    )
