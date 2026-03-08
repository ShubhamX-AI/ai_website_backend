import asyncio
import uuid

from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import (
    TOPIC_UI_FLASHCARD,
    TOPIC_GLOBAL_PRESENCE,
    TOPIC_NEARBY_OFFICES,
)


class UIPublisherToolsMixin:
    """Tools for publishing UI content (flashcards, global presence, nearby offices) to the frontend."""

    @function_tool
    async def publish_ui_stream(
        self, context: RunContext, user_input: str, agent_response: str
    ) -> str:
        """Tool used to publish the UI stream to the frontend."""
        self.logger.info(f"Publishing UI stream for: {user_input}")

        self._set_last_ui_snapshot(
            snapshot_type="flashcard_stream",
            title="Knowledge summary",
            summary=agent_response,
            details={"user_input": user_input},
            source_tool="publish_ui_stream",
        )

        # This runs in the background to ensure the voice response isn't delayed
        asyncio.create_task(
            self._publish_ui_stream(user_input, self.db_results, agent_response, self.user_id)
        )
        return "UI stream published."

    @function_tool
    async def recall_and_republish_ui_content(
        self, context: RunContext, agent_response: str
    ) -> str:
        """
        Recall and re-publish a previously displayed UI flashcard set from memory.
        Use this when the user asks to go back, see previous content, or revisit
        a topic that was already shown on screen.

        Args:
            agent_response: A short description of the content the user wants to see again,
                   interpreted by you based on user intent (e.g. 'services').
        """
        self.logger.info("🔁 Recall UI content requested for: '%s'", agent_response)

        if not self.user_id:
            return (
                "I don't have your user information yet, so I can't retrieve "
                "your previous session content. Could you please introduce yourself?"
            )

        cards = await self.ui_agent_functions.recall_ui_content(
            agent_response=agent_response, user_id=self.user_id
        )

        if not cards:
            return (
                f"I couldn't find any previously shown content matching '{agent_response}'. "
                "Would you like me to fetch that information fresh for you?"
            )

        # Re-publish the exact same cards from memory
        stream_id = str(uuid.uuid4())
        for card_index, card in enumerate(cards):
            card["stream_id"] = stream_id
            card["card_index"] = card_index
            card["recalled"] = True  # flag so frontend knows it's a replay
            await self._publish_data_packet(card, TOPIC_UI_FLASHCARD)

        # End-of-stream marker
        await self._publish_data_packet(
            {
                "type": "end_of_stream",
                "stream_id": stream_id,
                "card_count": len(cards),
            },
            TOPIC_UI_FLASHCARD,
        )

        self.logger.info(
            "✅ Re-published %d recalled flashcard(s) for user %s",
            len(cards),
            self.user_id,
        )
        self._set_last_ui_snapshot(
            snapshot_type="flashcard_recall",
            title="Recalled content",
            summary=f"Re-displayed {len(cards)} flashcard(s) from previous session content.",
            details={"query": agent_response, "card_count": len(cards)},
            source_tool="recall_and_republish_ui_content",
        )
        return f"Re-displayed {len(cards)} flashcard(s) from your previous session."

    @function_tool
    async def publisg_gloabl_pesense(
        self, context: RunContext, user_input: str = "global presence"
    ) -> str:
        """Publish Indus Net global presence details via data packet."""
        self.logger.info("Publishing global presence details via data packet")

        payload = {
            "type": "global_presence",
            "data": {
                "regions": {
                    "USA": "1310 S Vista Ave Ste 28, Boise, Idaho – 83705",
                    "Canada": "120 Adelaide Street West, Suite 2500, M5H 1T1",
                    "UK": "13 More London Riverside, London SE1 2RE",
                    "Poland": "BARTYCKA 22B M21A, 00-716 WARSZAWA",
                    "Singapore": "Indus Net Technologies PTE Ltd., 60 Paya Lebar Road, #09-43 Paya Lebar Square – 409051",
                },
                "headquarters": {
                    "Kolkata Sector 5": "4th Floor, SDF Building Saltlake Electronic Complex, Kolkata, West Bengal 700091",
                    "Kolkata Newtown": "4th Floor, Block-2b, ECOSPACE BUSINESS PARK, AA II, Newtown, Chakpachuria, West Bengal 700160",
                },
            },
        }

        await self._publish_data_packet(payload, TOPIC_GLOBAL_PRESENCE)
        self._set_last_ui_snapshot(
            snapshot_type="global_presence",
            title="Global presence",
            summary="Displayed Indus Net global and headquarters locations.",
            details=payload.get("data", {}),
            source_tool="publisg_gloabl_pesense",
        )
        return "Global presence data published."

    @function_tool
    async def publish_nearby_offices(self, context: RunContext, offices: list[dict]):
        """
        Publish a list of nearby office objects to the frontend via a data packet.
        Call this tool when the user asks for directions or nearby offices,
        after obtaining their location.

        Args:
            offices: A list of nearby office objects (each with 'id', 'name', 'address', and 'image_url').
        """
        self.logger.info(f"Publishing nearby offices to UI: {offices}")

        payload = {
            "type": "nearby_offices",
            "data": {
                "offices": offices,
            },
        }

        await self._publish_data_packet(payload, TOPIC_NEARBY_OFFICES)
        self._set_last_ui_snapshot(
            snapshot_type="nearby_offices",
            title="Nearby offices",
            summary=f"Displayed {len(offices)} nearby office option(s).",
            details=payload.get("data", {}),
            source_tool="publish_nearby_offices",
            links=[office.get("image_url") for office in offices if office.get("image_url")],
        )
        return "Nearby offices published to UI."

    @function_tool
    async def get_ui_history(self, context: RunContext) -> str:
        """
        Return the list of screens shown this session in order (oldest → newest).
        The current screen is marked with *.
        Call this BEFORE any back-navigation action to get the real server-tracked history.
        """
        titles = self._get_snapshot_history_titles()
        if not titles:
            return "No screen history yet this session."
        return "\n".join(titles)

    async def _publish_ui_stream(
        self, user_input: str, db_results: str, agent_response: str, user_id: str
    ) -> None:
        """Generate and publish UI cards, filtering out already-visible content."""
        stream_id = str(uuid.uuid4())
        card_index = 0

        async for payload in self.ui_agent_functions.query_process_stream(
            user_input=user_input,
            db_results=db_results,
            agent_response=agent_response,
            user_id=user_id,  # pass user_id so Mem0 can save the batch
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
