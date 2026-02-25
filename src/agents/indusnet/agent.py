import json
import asyncio
import uuid
import os
from typing import Optional
from livekit import rtc
from livekit.agents import function_tool, RunContext

from src.agents.base import BaseAgent
from src.agents.indusnet.prompts import INDUSNET_AGENT_PROMPT
from src.agents.prompts.humanization import TTS_HUMANIFICATION_CARTESIA
from src.services.openai.indusnet.openai_scv import UIAgentFunctions
from src.services.vectordb.vectordb_svc import VectorStoreService
from src.services.mail.calender_invite import send_calendar_invite
from src.services.map.googlemap.services import GoogleMapService
import datetime as dt

# Constants
FRONTEND_CONTEXT = ["ui.context", "user.context", "user.location"]
TOPIC_UI_FLASHCARD = "ui.flashcard"
TOPIC_CONTACT_FORM = "ui.contact_form"
TOPIC_USER_LOCATION = "user.location"          # frontend → backend: GPS result
TOPIC_UI_LOCATION_REQUEST = "ui.location_request"  # backend → frontend: request GPS
SKIPPED_METADATA_KEYS = ["source_content_focus"]


class IndusNetAgent(BaseAgent):
    """Agent for handling Indus Net Technologies inquiries with UI integration."""

    def __init__(self, room) -> None:
        self._base_instruction = INDUSNET_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA
        super().__init__(room=room, instructions=self._base_instruction)

        self.ui_agent_functions = UIAgentFunctions()
        self.vector_store = VectorStoreService()
        self.google_map_service = GoogleMapService()
        self.db_fetch_size = 10
        self.db_results = ""

        # Context State
        self.user_id: Optional[str] = None
        self.user_name: Optional[str] = None
        self.user_email: Optional[str] = None
        self.user_phone: Optional[str] = None
        self._active_elements: list[str] = []

        # Location State
        self._location_status: Optional[str] = None   # "success" | "denied" | "unsupported"
        self._user_lat: Optional[float] = None
        self._user_lng: Optional[float] = None
        self._location_accuracy: Optional[float] = None
        self._location_event = asyncio.Event()          # fired when frontend responds


    @function_tool
    async def search_indus_net_knowledge_base(self, context: RunContext, question: str):
        """Search the official Indus Net Knowledge Base for information about the company."""
        self.logger.info(f"Searching knowledge base for: {question}")
        # Fix: await the search to ensure db_results is populated before returning
        await self._vector_db_search(question)
        return self.db_results

    @function_tool
    async def publish_ui_stream(
        self, context: RunContext, user_input: str, agent_response: str
    ) -> str:
        """Tool used to publish the UI stream to the frontend."""
        self.logger.info(f"Publishing UI stream for: {user_input}")

        # This runs in the background to ensure the voice response isn't delayed
        asyncio.create_task(
            self._publish_ui_stream(user_input, self.db_results, agent_response)
        )
        return "UI stream published."


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

        payload = {
            "type": "contact_form_submit",
            "data": {
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "contact_details": contact_details,
            },
        }

        await self._publish_data_packet(payload, TOPIC_CONTACT_FORM)

        return "Contact form submitted successfully. A consultant will reach out soon."

    @function_tool
    async def schedule_meeting(
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
        Schedule a meeting and send a calendar invite.

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
            duration_hours
        )

        if success:
            return f"Meeting '{subject}' scheduled and invite sent to {recipient_email}."
        else:
            return f"Failed to send the meeting invite. Please check the logs."

    @function_tool
    async def get_user_info(
        self, context: RunContext, user_name: str, user_email: str = "", user_phone: str = ""
    ):
        """Get user information."""
        self.logger.info(f"Retrieving user information for: {user_name}")

        # Publish user information via data packet
        payload = {
            "user_name": user_name,
            "user_email": user_email,
            "user_phone": user_phone,
            "user_id": self.user_id,
        }
        topic = "user.details"
        await self._publish_data_packet(payload, topic)
        return "User information published."

    @function_tool
    async def request_user_location(self, context: RunContext):
        """
        Ask the frontend to share the user's current GPS location.
        The browser will prompt the user for permission. Returns the location
        status once the frontend responds (success, denied, or unsupported).
        Wait for this tool's result before calling calculate_distance_to_destination.
        """
        self.logger.info("📍 Requesting user location from frontend")

        # Reset previous state and the event flag so we wait for a fresh reply
        self._location_status = None
        self._user_lat = None
        self._user_lng = None
        self._location_accuracy = None
        self._location_event.clear()

        # Tell the frontend to fire the Geolocation API.
        # The frontend listens on topic 'ui.location_request' OR checks data.type === 'location_request'.
        await self._publish_data_packet(
            {"type": "location_request"},
            TOPIC_UI_LOCATION_REQUEST,
        )

        # Wait up to 15 s for the frontend to respond
        try:
            await asyncio.wait_for(self._location_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            return "Location request timed out. The user may not have responded to the browser prompt."

        if self._location_status == "success":
            accuracy_note = (
                f" (accuracy: ±{self._location_accuracy:.0f} m)"
                if self._location_accuracy is not None
                else ""
            )

            # Get location of the user
            location = await self.google_map_service.get_current_location(self._user_lat, self._user_lng)
            formatted_address = location.get("formatted_address", f"{self._user_lat},{self._user_lng}")
            return (
                f"Location obtained: lat={self._user_lat}, lng={self._user_lng}{accuracy_note}. "
                f"Address of the user: {formatted_address}. "
                "You can now call calculate_distance_to_destination."
            )
        elif self._location_status == "denied":
            return "The user denied location access or the request timed out on the browser side. Cannot calculate distance without location."
        elif self._location_status == "unsupported":
            return "The user's browser does not support Geolocation. Cannot calculate distance."
        else:
            return "Unknown location status received from the frontend."

    @function_tool
    async def calculate_distance_to_destination(
        self, context: RunContext, destination: str
    ):
        """
        Calculate the driving distance and estimated travel time from the user's
        current GPS location to a destination address or landmark.

        IMPORTANT: You MUST call request_user_location first and confirm a
        'success' status before calling this tool.

        Args:
            destination: The destination address or place name (e.g., "Indus Net Technologies, Kolkata").
        """
        if self._location_status != "success" or self._user_lat is None or self._user_lng is None:
            return (
                "I don't have the user's location yet. "
                "Please call request_user_location first and ensure access was granted."
            )

        self.logger.info(
            f"📐 Calculating distance from ({self._user_lat}, {self._user_lng}) to '{destination}'"
        )

        try:
            result = await self.google_map_service.get_directions(
                origin_lat=self._user_lat,
                origin_lng=self._user_lng,
                destination=destination
            )

            if not result:
                return f"Could not geocode '{destination}'. Please check the address and try again."

            if "error" in result:
                return f"The destination '{result['formatted_address']}' was found, but: {result['error']}."

            formatted_address = result["formatted_address"]
            distance_text = result["distance_text"]
            duration_text = result["duration_text"]
            polyline = result["polyline"]

            self.logger.info(f"✅ Distance to '{formatted_address}': {distance_text} ({duration_text})")

            # Publish polyline to the frontend
            await self._publish_data_packet({
                "type": "map.polyline",
                "data": {
                    "polyline": polyline
                }
            }, TOPIC_UI_LOCATION_REQUEST)

            return (
                f"The destination '{formatted_address}' is approximately {distance_text} away "
                f"and will take around {duration_text} by car from your current location."
            )

        except Exception as e:
            self.logger.error(f"❌ Distance calculation failed: {e}")
            return "An error occurred while calculating the distance. Please try again."

    # Handle data from the frontend
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
            asyncio.create_task(self._update_ui_context(context_payload))

        if topic == "user.context":
            self.logger.info("📱 User Context Sync received: %s", context_payload)

            user_info = context_payload.get("user_info", {})
            self.user_id = user_info.get("user_id")
            self.user_name = user_info.get("user_name")
            self.user_email = user_info.get("user_email")
            self.user_phone = user_info.get("user_phone")

            if self.user_name and self.user_name.lower() != "guest":
                asyncio.create_task(self._update_instructions())

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
                    self._user_lat, self._user_lng, self._location_accuracy,
                )
            else:
                error = context_payload.get("error", "unknown error")
                self.logger.warning("📍 Location not available: %s", error)

            # Unblock the coroutine waiting in request_user_location
            self._location_event.set()
            return False

    # ==================== Private Helper Methods ====================

    def _extract_payload_text(self, data: rtc.DataPacket) -> Optional[str]:
        """Extract and decode payload text from data packet."""
        payload = getattr(data, "data", None)
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="ignore")
        return str(payload) if payload is not None else None

    async def _publish_data_packet(self, payload: dict, topic: str) -> bool:
        """Publish a single data packet to the room."""
        try:
            await self.room.local_participant.publish_data(
                json.dumps(payload, default=str).encode("utf-8"),
                reliable=True,
                topic=topic,
            )
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to publish data: {e}")
            return False

    async def _publish_ui_stream(
        self, user_input: str, db_results: str, agent_response: str
    ) -> None:
        """Generate and publish UI cards, filtering out already-visible content."""
        stream_id = str(uuid.uuid4())
        card_index = 0

        async for payload in self.ui_agent_functions.query_process_stream(
            user_input=user_input, db_results=db_results, agent_response=agent_response
        ):
            title = payload.get("title", "")

            # Inject grouping info
            payload["stream_id"] = stream_id
            payload["card_index"] = card_index

            if await self._publish_data_packet(payload, TOPIC_UI_FLASHCARD):
                self.logger.info(
                    "✅ Data packet sent successfully: %s (Stream: %s, Index: %s)",
                    title,
                    stream_id,
                    card_index,
                )

            card_index += 1

        # Send end-of-stream marker
        end_of_stream_payload = {
            "type": "end_of_stream",
            "stream_id": stream_id,
            "card_count": card_index,
        }

        if await self._publish_data_packet(end_of_stream_payload, TOPIC_UI_FLASHCARD):
            self.logger.info(f"✅ End-of-stream marker sent for stream: {stream_id}")

    def _format_metadata_value(self, key: str, val: str) -> Optional[str]:
        """Format a single metadata value, handling JSON strings."""
        human_key = key.replace("_", " ").title()

        # Check if it's a JSON string (list or dict)
        if isinstance(val, str) and val.strip().startswith(("[", "{")):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    formatted_val = ", ".join(map(str, parsed))
                elif isinstance(parsed, dict):
                    formatted_val = ", ".join(
                        [
                            f"{k.replace('_', ' ').title()}: {v}"
                            for k, v in parsed.items()
                        ]
                    )
                else:
                    formatted_val = str(parsed)
                return f"**{human_key}:** {formatted_val}"
            except json.JSONDecodeError:
                # Fallback for invalid JSON
                return f"**{human_key}:** {val}"

        # Regular value
        return f"**{human_key}:** {val}"

    def _format_metadata(self, metadata: dict) -> list[str]:
        """Extract and format all metadata dynamically."""
        details = []
        for key, val in metadata.items():
            # Skip internal/empty keys
            if not val or key in SKIPPED_METADATA_KEYS:
                continue

            formatted = self._format_metadata_value(key, val)
            if formatted:
                details.append(formatted)

        return details

    async def _vector_db_search(self, query: str) -> str:
        """Search the vector database for relevant information."""
        results = await self.vector_store.search(query, k=self.db_fetch_size)

        formatted_results = []
        for i, doc in enumerate(results):
            content = doc.page_content.strip()
            md_chunk = f"### Result {i + 1}\n\n{content}\n"

            # Format metadata
            details = self._format_metadata(doc.metadata)
            if details:
                md_chunk += "\n" + "\n".join([f"- {d}" for d in details])

            formatted_results.append(md_chunk)

        self.db_results = "\n\n---\n\n".join(formatted_results)
        self.logger.info(f"✅ DB results converted to markdown")
        return self.db_results

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

    async def _update_instructions(self) -> None:
        """Rebuild and inject current UI and User state into agent instructions."""
        self.logger.debug("Rebuilding agent instructions with full context")

        # 1. Start with base instructions
        new_instructions = f"{self._base_instruction}\n\n"

        # 2. Add User Context
        if self.user_name and self.user_name.lower() != "guest":
            self.logger.info(
                f"Adding user context to agent instructions for {self.user_name}, {self.user_email}"
            )

            new_instructions += (
                f"### Current User Information:\n"
                f"- **Name**: {self.user_name}\n"
                f"- **Email**: {self.user_email or 'Not provided'}\n"
                f"- **Phone**: {self.user_phone or 'Not provided'}\n"
                f"Greet the user by their name and use this context to personalize your response.\n\n"
            )
        else:
            new_instructions += (
                f"### User Identity: Unknown\n"
                f"The user is currently a Guest. You MUST naturally ask for their name. "
                f"ONCE they provide it, you MUST spell it out for confirmation before proceeding with any data capture.\n\n"
            )

        # 3. Add UI Context
        if self._active_elements:
            active_elements_md = "\n".join(
                f"- {element}" for element in self._active_elements
            )
            new_instructions += (
                f"### Elements Currently Present in UI:\n"
                f"{active_elements_md}\n"
                f"Use this to refer to what the user is seeing or to avoid repeating visible content.\n"
            )

        # Update the LLM system prompt
        await self.update_instructions(new_instructions)
