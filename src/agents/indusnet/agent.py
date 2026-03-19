from src.agents.base import BaseAgent
from src.agents.indusnet.prompts import INDUSNET_AGENT_PROMPT
from src.agents.prompts.humanization import TTS_HUMANIFICATION_CARTESIA
from src.services.llm.ui_agent import UIAgentFunctions
from src.services.vectordb.vectordb_svc import VectorStoreService
from src.services.map.googlemap.services import GoogleMapService
from src.services.search.searxng_svc import SearXNGService

# ── Helpers ────────────────────────────────────────────────────────────────
from src.agents.indusnet.helpers.packet import PacketHelperMixin
from src.agents.indusnet.helpers.vector_search import VectorSearchHelperMixin

# ── Handlers ───────────────────────────────────────────────────────────────
from src.agents.indusnet.handlers.data_handler import DataHandlerMixin

# ── Tools ──────────────────────────────────────────────────────────────────
from src.agents.indusnet.tools.knowledge import KnowledgeToolsMixin
from src.agents.indusnet.tools.ui_publisher import UIPublisherToolsMixin
from src.agents.indusnet.tools.forms import FormToolsMixin
from src.agents.indusnet.tools.location import LocationToolsMixin
from src.agents.indusnet.tools.meeting import MeetingToolsMixin
from src.agents.indusnet.tools.email import EmailToolsMixin
from src.agents.indusnet.tools.whatsapp import WhatsAppToolsMixin
from src.agents.indusnet.tools.user import UserToolsMixin
from src.agents.indusnet.tools.endcall import EndCallToolsMixin

# ── State ──────────────────────────────────────────────────────────────────
from src.agents.indusnet.state import AgentState


class IndusNetAgent(
    # ── State (must come before tools that reference state fields) ──
    AgentState,
    # ── Low-level I/O ──────────────────────────────────────────────
    PacketHelperMixin,
    VectorSearchHelperMixin,
    # ── Data Handler ───────────────────────────────────────────────
    DataHandlerMixin,
    # ── Tools (registered as @function_tool by LiveKit) ────────────
    KnowledgeToolsMixin,
    UIPublisherToolsMixin,
    FormToolsMixin,
    LocationToolsMixin,
    MeetingToolsMixin,
    EmailToolsMixin,
    WhatsAppToolsMixin,
    UserToolsMixin,
    EndCallToolsMixin,
    # ── Base ───────────────────────────────────────────────────────
    BaseAgent,
):
    """
    Agent for handling Indus Net Technologies inquiries with UI integration.

    This class is intentionally thin — it only wires together:
      - Service clients (VectorStore, UIAgentFunctions, GoogleMapService)
      - State initialisation (via AgentState mixin)
      - Instruction rebuilding (_update_instructions)

    All tool logic lives in tools/, all packet I/O in helpers/,
    all data-event handling in handlers/, and all constants in constants.py.
    """

    def __init__(self, room) -> None:
        self._base_instruction = INDUSNET_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA
        super().__init__(room=room, instructions=self._base_instruction)

        # ── Service Clients ────────────────────────────────────────
        self.ui_agent_functions = UIAgentFunctions()
        self.vector_store = VectorStoreService()
        self.search_service = SearXNGService()
        self.google_map_service = GoogleMapService()

        # ── Runtime State (all fields defined in AgentState) ───────
        self._init_state()

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
                f"ONCE they provide it, Don't spell it out for confirmation, just proceed with any data capture.\n\n"
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
