import json
import asyncio
import uuid
from typing import Optional
from livekit import rtc
from livekit.agents import function_tool, RunContext

from src.agents.base import BaseAgent
from src.agents.indusnet.prompts import INDUSNET_AGENT_PROMPT
from src.agents.prompts.humanization import TTS_HUMANIFICATION_CARTESIA
from src.services.openai.indusnet.openai_scv import UIAgentFunctions
from src.services.vectordb.vectordb_svc import VectorStoreService

# Constants
TOPIC_UI_CONTEXT = "ui.context"
TOPIC_UI_FLASHCARD = "ui.flashcard"
SKIPPED_METADATA_KEYS = ["source_content_focus"]


class IndusNetAgent(BaseAgent):
    """Agent for handling Indus Net Technologies inquiries with UI integration."""

    def __init__(self, room) -> None:
        self._base_instruction = INDUSNET_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA
        super().__init__(room=room, instructions=self._base_instruction)
        
        self.ui_agent_functions = UIAgentFunctions()
        self.vector_store = VectorStoreService()
        self.db_fetch_size = 5
        self.db_results = ""

    @property
    def welcome_message(self):
        return "Welcome to Indus Net Technologies. Tell me how can I help you today?"

    @function_tool
    async def search_indus_net_knowledge_base(self, context: RunContext, question: str):
        """Search the official Indus Net Knowledge Base for information about the company."""
        self.logger.info(f"Searching knowledge base for: {question}")
        # Fix: await the search to ensure db_results is populated before returning
        await self._vector_db_search(question)
        return self.db_results

    @function_tool
    async def publish_ui_stream(self, context: RunContext, user_input: str, agent_response: str) -> str:
        """Tool used to publish the UI stream to the frontend."""
        self.logger.info(f"Publishing UI stream for: {user_input}")
        
        # This runs in the background to ensure the voice response isn't delayed
        asyncio.create_task(self._publish_ui_stream(user_input, self.db_results, agent_response))
        return "UI stream published."

    # Handle data from the frontend
    def handle_data(self, data: rtc.DataPacket):
        """Handle incoming data packets from the room."""
        topic = getattr(data, "topic", None)
        
        if topic not in [TOPIC_UI_CONTEXT]:
            return

        payload_text = self._extract_payload_text(data)
        if not payload_text:
            return

        try:
            context_payload = json.loads(payload_text)
        except json.JSONDecodeError:
            self.logger.warning(f"Invalid payload for topic {topic} - JSON parse failed")
            return

        if topic == TOPIC_UI_CONTEXT:
            self.logger.info("📱 UI Context Sync received")
            asyncio.create_task(self._update_ui_context(context_payload))

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
                json.dumps(payload).encode("utf-8"),
                reliable=True,
                topic=topic,
            )
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to publish data: {e}")
            return False

    async def _publish_ui_stream(self, user_input: str, db_results: str, agent_response: str) -> None:
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
                    title, stream_id, card_index
                )
            
            card_index += 1

        # Send end-of-stream marker
        end_of_stream_payload = {
            "type": "end_of_stream",
            "stream_id": stream_id,
            "card_count": card_index
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
                    formatted_val = ", ".join([
                        f"{k.replace('_', ' ').title()}: {v}" 
                        for k, v in parsed.items()
                    ])
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
            md_chunk = f"### Result {i+1}\n\n{content}\n"
            
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
            "active_elements": context_payload.get("active_elements", [])
        }

        # Update the UI agent with the UI context
        await self.ui_agent_functions.update_instructions_with_context(ui_context)
        
        # Update the agent instructions with current active elements/UI state
        await self._update_instructions_with_context(ui_context["active_elements"])

    async def _update_instructions_with_context(self, active_elements: list = None) -> None:
        """Inject current UI state into agent instructions."""
        if not active_elements:
            return

        self.logger.debug("Agent instructions updated with UI context")
        
        # Convert active elements to markdown
        active_elements_md = "\n".join(f"- {element}" for element in active_elements)
        new_instructions = (
            f"{self._base_instruction}\n\n"
            f"Elements Currently Present in UI:\n{active_elements_md}"
        )

        # Update the LLM system prompt
        await self.update_instructions(new_instructions)