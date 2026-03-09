import datetime as dt

from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import TOPIC_WHATSAPP_DELIVERY
from src.services.whatsapp.context_whatsapp import send_context_whatsapp


class WhatsAppToolsMixin:
    """Tools for sending contextual screen summaries via WhatsApp."""

    async def _resolve_snapshot(self, screens_back: int = 0) -> dict | None:
        """
        Return the best available snapshot for WhatsApp composition.

        Priority:
        1. Session history at pointer offset (fast, exact, current session).
        2. Mem0 vector recall (cross-session fallback when session is empty).
        """
        snapshot = self._get_snapshot_at_offset(-screens_back)
        if snapshot:
            return snapshot

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
    async def send_context_whatsapp(
        self,
        context: RunContext,
        recipient_phone: str = "",
        screens_back: int = 0,
    ) -> str:
        """
        Send a structured summary via WhatsApp.

        Args:
            recipient_phone: WhatsApp phone number (10-15 digits, e.g., 918697421450).
            screens_back: How many screens back to pull content from.
                          0 = current screen, 1 = one screen back, 2 = two screens back.
        """
        snapshot = await self._resolve_snapshot(screens_back)
        if not snapshot:
            return (
                "I do not have recent on-screen context to send via WhatsApp yet. "
                "Please ask me to show details first."
            )

        if not recipient_phone:
            return "Please provide the WhatsApp phone number where I should send this."

        from src.services.whatsapp.context_whatsapp import (
            send_context_whatsapp,
            is_valid_phone_number,
        )

        if not is_valid_phone_number(recipient_phone):
            return (
                "That phone number looks invalid. Please provide a valid WhatsApp number "
                "(10-15 digits, e.g., 918697421450)."
            )

        snapshot_type = snapshot.get("type", "unknown")

        success, message = await send_context_whatsapp(
            recipient_phone,
            snapshot,
            self.user_name,
        )

        status_payload = {
            "type": "context_whatsapp_delivery",
            "data": {
                "recipient_phone": recipient_phone,
                "snapshot_type": snapshot_type,
                "screens_back": screens_back,
                "status": "sent" if success else "failed",
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        }
        await self._publish_data_packet(status_payload, TOPIC_WHATSAPP_DELIVERY)

        if success:
            self._last_whatsapp_recipient = recipient_phone
            self._last_whatsapp_sent_at = dt.datetime.now(dt.timezone.utc).isoformat()
            screens_note = (
                f" (from {screens_back} screen(s) back)" if screens_back else ""
            )
            return f"Done. I sent the summary via WhatsApp{screens_note} to {recipient_phone}."

        return f"I could not send the WhatsApp message to {recipient_phone}. {message}"
