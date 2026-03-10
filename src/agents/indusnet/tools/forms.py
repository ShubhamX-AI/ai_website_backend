import asyncio

from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import (
    TOPIC_CONTACT_FORM,
    TOPIC_JOB_APPLICATION,
)
from src.services.mail.submission_receipt import send_submission_receipt


def _spoken_reference(reference_id: str) -> str:
    suffix = reference_id[-6:] if len(reference_id) > 6 else reference_id
    return f"reference ending in {suffix}"


class FormToolsMixin:
    """Tools for the contact form and job application workflows."""

    @function_tool
    async def preview_contact_form(
        self,
        context: RunContext,
        user_name: str,
        user_email: str,
        user_phone: str,
        contact_details: str,
    ):
        """
        Send the contact form data to the frontend for user review.

        Args:
            user_name: The name of the user.
            user_email: The email of the user.
            user_phone: The phone number of the user.
            contact_details: The reason or details the user provided for contacting.
        """
        self.logger.info(
            f"Sending contact form to the UI: {user_name} | {user_email} | {user_phone} | Details: {contact_details}"
        )

        payload = {
            "type": "contact_form",
            "data": {
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "contact_details": contact_details,
            },
        }

        # Mock sending process
        await asyncio.sleep(2.0)
        await self._publish_data_packet(payload, TOPIC_CONTACT_FORM)
        self._set_last_ui_snapshot(
            snapshot_type="contact_form_preview",
            title="Contact form preview",
            summary="Displayed contact form details for user review.",
            details=payload.get("data", {}),
            source_tool="preview_contact_form",
        )

        return "Contact form displayed on UI. Please ask the user to review the details and confirm before submission."

    @function_tool
    async def submit_contact_form(
        self,
        context: RunContext,
        user_name: str,
        user_email: str,
        user_phone: str,
        contact_details: str,
    ):
        """
        Submit the contact form data to the company after user confirmation.

        Args:
            user_name: The name of the user.
            user_email: The email of the user.
            user_phone: The phone number of the user.
            contact_details: The reason or details the user provided for contacting.
        """
        self.logger.info(
            f"Sending contact form: {user_name} | {user_email} | {user_phone} | Details: {contact_details}"
        )

        # Mock sending process
        await asyncio.sleep(0.5)
        receipt_result = await send_submission_receipt(
            recipient_email=user_email,
            submission_type="contact_form",
            user_name=user_name,
            user_phone=user_phone,
            detail_value=contact_details,
        )

        payload = {
            "type": "contact_form_submit",
            "data": {
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "contact_details": contact_details,
                "reference_id": receipt_result.reference_id,
                "submitted_at": receipt_result.submitted_at,
                "receipt_email_sent": receipt_result.sent,
            },
        }

        await self._publish_data_packet(payload, TOPIC_CONTACT_FORM)
        self._set_last_ui_snapshot(
            snapshot_type="contact_form_submitted",
            title="Contact form submitted",
            summary=(
                f"Recorded contact form details with reference ID {receipt_result.reference_id}."
            ),
            details=payload.get("data", {}),
            source_tool="submit_contact_form",
        )

        if receipt_result.sent:
            return (
                "Contact form submitted successfully. "
                f"I emailed a receipt to {user_email} with the full tracking details, including the {_spoken_reference(receipt_result.reference_id)}."
            )

        self.logger.warning(
            "Contact form receipt email failed for %s: %s",
            user_email,
            receipt_result.message,
        )
        return (
            "Contact form submitted successfully, but I could not email the receipt right now. "
            f"I still saved it under the {_spoken_reference(receipt_result.reference_id)}."
        )

    @function_tool
    async def preview_job_application(
        self,
        context: RunContext,
        user_name: str,
        user_email: str,
        user_phone: str,
        job_details: str,
    ):
        """
        Send the job application data to the frontend for user review.

        Args:
            user_name: The name of the user.
            user_email: The email of the user.
            user_phone: The phone number of the user.
            job_details: The job or career opening the user is applying for.
        """
        self.logger.info(
            f"Sending job application to the UI: {user_name} | {user_email} | {user_phone} | Job: {job_details}"
        )

        payload = {
            "type": "job_application_preview",
            "data": {
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "job_details": job_details,
            },
        }

        # Mock sending process
        await asyncio.sleep(2.0)
        await self._publish_data_packet(payload, TOPIC_JOB_APPLICATION)
        self._set_last_ui_snapshot(
            snapshot_type="job_application_preview",
            title="Job application preview",
            summary="Displayed job application details for user review.",
            details=payload.get("data", {}),
            source_tool="preview_job_application",
        )

        return "Job application form displayed on UI. Please ask the user to review the details and confirm before submission."

    @function_tool
    async def submit_job_application(
        self,
        context: RunContext,
        user_name: str,
        user_email: str,
        user_phone: str,
        job_details: str,
    ):
        """
        Submit the job application data after user confirmation.

        Args:
            user_name: The name of the user.
            user_email: The email of the user.
            user_phone: The phone number of the user.
            job_details: The job or career opening the user is applying for.
        """
        self.logger.info(
            f"Submitting job application: {user_name} | {user_email} | {user_phone} | Job: {job_details}"
        )

        # Mock sending process
        await asyncio.sleep(0.5)
        receipt_result = await send_submission_receipt(
            recipient_email=user_email,
            submission_type="job_application",
            user_name=user_name,
            user_phone=user_phone,
            detail_value=job_details,
        )

        payload = {
            "type": "job_application_submit",
            "data": {
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "job_details": job_details,
                "reference_id": receipt_result.reference_id,
                "submitted_at": receipt_result.submitted_at,
                "receipt_email_sent": receipt_result.sent,
            },
        }

        await self._publish_data_packet(payload, TOPIC_JOB_APPLICATION)
        self._set_last_ui_snapshot(
            snapshot_type="job_application_submitted",
            title="Job application submitted",
            summary=(
                "Recorded job application details with reference ID "
                f"{receipt_result.reference_id}."
            ),
            details=payload.get("data", {}),
            source_tool="submit_job_application",
        )

        if receipt_result.sent:
            return (
                "Job application submitted successfully. "
                f"I emailed a receipt to {user_email} with the full tracking details, including the {_spoken_reference(receipt_result.reference_id)}."
            )

        self.logger.warning(
            "Job application receipt email failed for %s: %s",
            user_email,
            receipt_result.message,
        )
        return (
            "Job application submitted successfully, but I could not email the receipt right now. "
            f"I still saved it under the {_spoken_reference(receipt_result.reference_id)}."
        )
