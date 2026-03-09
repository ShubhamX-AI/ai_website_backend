import asyncio
import datetime as dt
from functools import partial

from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import TOPIC_EMAIL_DELIVERY
from src.services.mail.context_email import (
    compose_context_email,
    is_valid_email_address,
    send_context_email,
)


class EmailToolsMixin:
    """Tools for sending contextual screen summaries via email."""

    _LOW_RISK_SNAPSHOT_TYPES = {
        "flashcard_stream",
        "flashcard_recall",
        "global_presence",
        "nearby_offices",
        "distance_map",
        "meeting_preview",
        "mem0_recall",
    }

    async def _resolve_snapshot(self, screens_back: int = 0) -> dict | None:
        """
        Return the best available snapshot for email composition.

        Priority:
        1. Session history at pointer offset (fast, exact, current session).
        2. Mem0 vector recall (cross-session fallback when session is empty).
        """
        snapshot = self._get_snapshot_at_offset(-screens_back)
        if snapshot:
            return snapshot

        # Fallback: try Mem0 when session history is empty
        if self.user_id:
            self.logger.info("📭 Session snapshot empty — falling back to Mem0 recall")
            try:
                cards = await self.ui_agent_functions.recall_ui_content(
                    agent_response="most recent content shown to user",
                    user_id=self.user_id,
                )
                if cards:
                    combined_summary = " ".join(
                        c.get("value") or c.get("content") or c.get("title", "")
                        for c in cards[:3]
                    )[:600]
                    return {
                        "type": "mem0_recall",
                        "title": cards[0].get("title", "Recalled content"),
                        "summary": combined_summary,
                        "details": {"card_count": len(cards), "source": "Mem0"},
                        "source_tool": "mem0_recall",
                        "email_context": {
                            "heading": cards[0].get("title", "Recalled content"),
                            "context_line": "A concise recap of previously shared information.",
                            "raw_summary": combined_summary,
                        },
                        "links": [],
                        "timestamp": dt.datetime.utcnow().isoformat(),
                    }
            except Exception as exc:
                self.logger.warning("Mem0 recall fallback failed: %s", exc)

        return None

    @function_tool
    async def send_context_email(
        self,
        context: RunContext,
        recipient_email: str = "",
        screens_back: int = 0,
    ) -> str:
        """
        Send a polished summary email of on-screen context.

        Args:
            recipient_email: Optional recipient email. Uses known user email when omitted.
            screens_back: How many screens back to pull content from.
                          0 = current screen, 1 = one screen back, 2 = two screens back.
        """
        snapshot = await self._resolve_snapshot(screens_back)
        if not snapshot:
            return (
                "I do not have recent on-screen context to send yet. "
                "Please ask me to show details first."
            )

        to_email = (recipient_email or self.user_email or "").strip()
        if not to_email:
            return "I can send this right away. Which email address should I use?"

        if not is_valid_email_address(to_email):
            return "That email address appears invalid. Please provide a valid address."

        snapshot_type = snapshot.get("type", "unknown")

        loop = asyncio.get_event_loop()
        success, message = await loop.run_in_executor(
            None,
            send_context_email,
            to_email,
            snapshot,
            self.user_name,
        )

        status_payload = {
            "type": "context_email_delivery",
            "data": {
                "recipient_email": to_email,
                "snapshot_type": snapshot_type,
                "screens_back": screens_back,
                "status": "sent" if success else "failed",
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        }
        await self._publish_data_packet(status_payload, TOPIC_EMAIL_DELIVERY)

        if success:
            self._last_email_recipient = to_email
            self._last_email_sent_at = dt.datetime.now(dt.timezone.utc).isoformat()
            screens_note = (
                f" (from {screens_back} screen(s) back)" if screens_back else ""
            )
            return f"Done. I sent the summary email{screens_note} to {to_email}."

        return f"I could not send the email to {to_email}. {message}"
