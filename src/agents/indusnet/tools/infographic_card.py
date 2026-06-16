from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import TOPIC_UI_INFOGRAPHIC
from src.services.llm.infographic import build_simple_infographic


class InfographicToolsMixin:
    """Tool for publishing a text INFOGRAPHIC card to the user's screen.

    An infographic carries NO images — that is the job of the UI image card
    ('publish_ui_stream'). It is for text-led answers that deserve fuller,
    well-structured text than a terse image flashcard: pricing, process,
    explainers, partners, comparisons, greetings, and general replies. The main
    agent LLM authors the content directly; it is rendered as the same composed
    infographic (hero + sections) the UI engine produces. Use 'publish_ui_stream'
    instead when you want the UI engine to compose a richer multi-block layout.
    """

    @function_tool
    async def publish_infographic(
        self,
        context: RunContext,
        title: str,
        markdown_content: str,
        bullets: list[str] | None = None,
        chips: list[str] | None = None,
        visual_intent: str = "neutral",
        icon: str = "info",
    ) -> str:
        """
        Render a polished text INFOGRAPHIC card on the user's screen. NO images — this
        card is text-led; use 'publish_ui_stream' when the topic warrants image flashcards
        or a richer multi-block infographic (see ui_publishing_policy). An infographic can
        hold MORE and LONGER structured text than a UI image card.

        Do NOT call this when 'publish_ui_stream' or any dedicated screen tool
        (publisg_gloabl_pesense, publish_nearby_offices, publish_office_details,
        preview_contact_form, preview_job_application, preview_meeting_invite,
        calculate_distance_to_destination) is already being called this turn — pick
        ONE visual per turn. The markdown is rendered visually only; your SPOKEN reply
        must stay plain prose. IMPORTANT: this REPLACES everything currently on screen.

        Args:
            title: A short, scannable headline (3-8 words).
            markdown_content: The card body as rich markdown (paragraphs, **bold**).
                Can be richer and longer than a UI image card's terse bullets.
            bullets: Optional short feature/checklist items rendered as a checked list.
            chips: Optional tag pills shown at the foot of the card (e.g. industries).
            visual_intent: Card style — neutral|urgent|success|warning|processing.
            icon: A Lucide icon name for the card header (e.g. info, sparkles, user, phone).
        """
        self.logger.info(f"Publishing infographic card to the UI: {title}")

        payload = build_simple_infographic(
            title=title,
            markdown_content=markdown_content,
            bullets=bullets,
            chips=chips,
            visual_intent=visual_intent,
            icon=icon,
        )

        await self._publish_data_packet(payload, TOPIC_UI_INFOGRAPHIC)
        self._set_last_ui_snapshot(
            snapshot_type="infographic",
            title=title,
            summary=markdown_content[:120],
            details=payload,
            source_tool="publish_infographic",
        )

        return "Infographic card published to the screen."
