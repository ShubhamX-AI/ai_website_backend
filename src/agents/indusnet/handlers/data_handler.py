import json

from livekit import rtc

from src.agents.indusnet.constants import FRONTEND_CONTEXT


class DataHandlerMixin:
    """Handles all incoming data packets from the LiveKit room."""

    def handle_data(self, data: rtc.DataPacket):
        """Handle incoming data packets from the room."""
        topic = getattr(data, "topic", None)

        if topic not in FRONTEND_CONTEXT:
            return

        payload_text = self._extract_payload_text(data)
        if not payload_text:
            return

        try:
            context_payload = json.loads(payload_text)
        except json.JSONDecodeError:
            self.logger.warning(
                f"Invalid payload for topic {topic} - JSON parse failed"
            )
            return

        if topic == "ui.context":
            self.logger.info("📱 UI Context Sync received")
            # Ui context update is stopped fo now
            # asyncio.create_task(self._update_ui_context(context_payload))

        if topic == "user.context":
            self.logger.info("📱 User Context Sync received: %s", context_payload)

            user_info = context_payload.get("user_info", {})
            self.user_id = user_info.get("user_id")
            # Disabled: do NOT personalize from the user.context packet — the agent
            # must not know the user's name/email/phone, even for returning users.
            # self.user_name = user_info.get("user_name")
            # self.user_email = user_info.get("user_email")
            # self.user_phone = user_info.get("user_phone")

            # if self.user_name and self.user_name.lower() != "guest":
            #     asyncio.create_task(self._update_instructions())

            return False

        if topic == "user.location":
            status = context_payload.get("status")
            self.logger.info("📍 Location packet received — status: %s", status)

            self._location_status = status

            if status == "success":
                self._user_lat = context_payload.get("latitude")
                self._user_lng = context_payload.get("longitude")
                self._location_accuracy = context_payload.get("accuracy")
                self.logger.info(
                    "📍 Location: lat=%s, lng=%s, accuracy=%s m",
                    self._user_lat,
                    self._user_lng,
                    self._location_accuracy,
                )
            else:
                error = context_payload.get("error", "unknown error")
                self.logger.warning("📍 Location not available: %s", error)

            # Unblock the coroutine waiting in request_user_location
            self._location_event.set()
            return False

    async def _update_ui_context(self, context_payload: dict) -> None:
        """Process UI context sync from frontend and update agent state."""
        viewport = context_payload.get("viewport", {})
        capabilities = viewport.get("capabilities", {})

        # Extract data from the payload
        ui_context = {
            "screen": viewport.get("screen", "desktop"),
            "theme": viewport.get("theme", "light"),
            "max_visible_cards": capabilities.get("maxVisibleCards", 4),
            "active_elements": context_payload.get("active_elements", []),
        }

        # Update the UI agent with the UI context
        await self.ui_agent_functions.update_instructions_with_context(ui_context)

        # Update our state and rebuild the full prompt
        self._active_elements = ui_context.get("active_elements", [])
        await self._update_instructions()
