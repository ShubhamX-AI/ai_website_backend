import asyncio
import datetime as dt

from livekit.agents import function_tool, RunContext

from src.services.mail.calender_invite import send_calendar_invite
from src.agents.indusnet.constants import TOPIC_MEETING_FORM



class MeetingToolsMixin:
    """Tool for scheduling meetings and sending calendar invites."""

    @function_tool
    async def schedule_meeting(
        self,
        recipient_email: str,
        subject: str,
        description: str,
        location: str,
        start_time_iso: str,
        duration_hours: float = 1.0,
    ):
        """
        Schedule a meeting and send a calendar invite.
        Call this ONLY after the user has REVIEWED the 'preview_meeting_invite' visual
        and explicitly CONFIRMED (e.g., 'Yes, send the invite').

        Args:
            recipient_email: The email address to send the invite to.
            subject: The title of the meeting.
            description: A brief description of the meeting.
            location: Where the meeting will happen (e.g., 'Zoom', 'Office').
            start_time_iso: The start time in ISO 8601 format (e.g., '2026-02-21T14:00:00').
            duration_hours: How long the meeting lasts in hours (default: 1.0).
        """

        self.logger.info(f"Scheduling meeting for {recipient_email}: {subject}")

        try:
            start_time = dt.datetime.fromisoformat(start_time_iso)
        except ValueError:
            return "Invalid date format. Please use ISO format (YYYY-MM-DDTHH:MM:SS)."

        # Run the blocking send_calendar_invite in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            send_calendar_invite,
            recipient_email,
            subject,
            description,
            location,
            start_time,
            duration_hours,
        )

        if success:
            # Publish success status to the frontend
            payload = {
                "type": "meeting_invite_submit",
                "data": {
                    "recipient_email": recipient_email,
                    "subject": subject,
                    "start_time": start_time_iso,
                    "status": "sent"
                },
            }
            await self._publish_data_packet(payload, TOPIC_MEETING_FORM)
            self._set_last_ui_snapshot(
                snapshot_type="meeting_invite_sent",
                title="Meeting invite sent",
                summary=f"Meeting invite '{subject}' was sent to {recipient_email}.",
                details=payload.get("data", {}),
                source_tool="schedule_meeting",
            )

            return (
                f"Meeting '{subject}' scheduled and invite sent to {recipient_email}."
            )
        else:
            return f"Failed to send the meeting invite. Please check the logs."

    @function_tool
    async def preview_meeting_invite(
        self,
        context: RunContext,
        recipient_email: str,
        subject: str,
        description: str,
        location: str,
        start_time_iso: str,
        duration_hours: float = 1.0,
    ):
        """
        Send the meeting invitation data to the frontend for user review.

        Args:
            recipient_email: The email address for the invite.
            subject: The title of the meeting.
            description: A brief description of the meeting.
            location: Where the meeting will happen.
            start_time_iso: The start time in ISO 8601 format.
            duration_hours: How long the meeting lasts in hours.
        """
        self.logger.info(
            f"Sending meeting preview to the UI: {recipient_email} | {subject} | {start_time_iso}"
        )

        payload = {
            "type": "meeting_form",
            "data": {
                "recipient_email": recipient_email,
                "subject": subject,
                "description": description,
                "location": location,
                "start_time": start_time_iso,
                "duration_hours": duration_hours,
            },
        }

        # Small delay for visual effect
        await asyncio.sleep(1.5)
        await self._publish_data_packet(payload, TOPIC_MEETING_FORM)
        self._set_last_ui_snapshot(
            snapshot_type="meeting_preview",
            title="Meeting invitation preview",
            summary="Displayed meeting invitation details for review.",
            details=payload.get("data", {}),
            source_tool="preview_meeting_invite",
        )

        return "Meeting preview displayed on UI. Please ask the user to review the details and confirm before sending the invite."
