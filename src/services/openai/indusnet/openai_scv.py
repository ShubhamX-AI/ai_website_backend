from openai import AsyncOpenAI
from src.services.openai.indusnet.ui_system_prompt import UI_SYSTEM_INSTRUCTION
from typing import Any, AsyncGenerator, Optional
from mem0 import Memory
import json
import re
import os
import logging
from dotenv import load_dotenv
from src.core.config import settings

load_dotenv(override=True)


class UIAgentFunctions:
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.llm_model = "gpt-4o-mini"
        self.logger = logging.getLogger(__name__)
        self.instructions = UI_SYSTEM_INSTRUCTION

        # ── Mem0 Memory Setup ──────────────────────────────────────────────
        mem0_config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "api_key": os.getenv("OPENAI_API_KEY"),
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": os.getenv("OPENAI_API_KEY"),
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "ui_flashcard_memory",
                    "path": f"{settings.BASE_DIR}/src/services/vectordb/chroma_db_mem0",
                },
            },
        }
        self.memory = Memory.from_config(mem0_config)
        self.logger.info("✅ Mem0 memory initialized with ChromaDB backend")

    # ── Streaming Generation + Auto-Save ──────────────────────────────────

    async def query_process_stream(
        self,
        user_input: str,
        db_results: str,
        agent_response: str | None = None,
        user_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Generate flashcard payloads for the given user input and DB results.
        Automatically saves the full batch to Mem0 after streaming completes
        (only when user_id is provided).
        """
        try:
            self.logger.info("Starting UI stream generation ...")

            effective_agent_response = (
                agent_response or "Analyze DB Results to predict the response."
            )

            prompt_content = f"""
                ## User's Question
                {user_input}

                ## Agent's Spoken Response
                {effective_agent_response}

                ## Database Results (Raw Reference)
                {db_results}

                ## Your Task
                Generate 1 to 4 flashcards for NEW information only. Check active_elements and skip any content already displayed.
            """

            stream = await self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.instructions},
                    {"role": "user", "content": prompt_content},
                ],
                response_format={"type": "json_object"},
                stream=True,
                temperature=0.5,
            )

            generated_cards: list[dict] = []  # collect for Mem0 save

            async with stream:
                buffer = ""

                # --- STATES ---
                # 0: Searching for "cards": [
                # 1: Parsing Card Objects { ... }
                state = 0

                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content

                        # === STATE 0: LOOK FOR START OF CARDS ARRAY ===
                        if state == 0:
                            match = re.search(r'"cards"\s*:\s*\[', buffer)
                            if match:
                                buffer = buffer[match.end():]  # Cut past the [
                                state = 1

                        # === STATE 1: EXTRACT JSON OBJECTS ===
                        if state == 1:
                            while True:
                                start_idx = buffer.find("{")
                                if start_idx == -1:
                                    break

                                depth = 0
                                end_idx = -1

                                for k in range(start_idx, len(buffer)):
                                    if buffer[k] == "{":
                                        depth += 1
                                    elif buffer[k] == "}":
                                        depth -= 1
                                        if depth == 0:
                                            end_idx = k
                                            break

                                if end_idx != -1:
                                    raw_json = buffer[start_idx: end_idx + 1]

                                    try:
                                        card_obj = json.loads(raw_json)
                                        payload = await self._normalize_card_payload(
                                            card_obj
                                        )
                                        if payload:
                                            generated_cards.append(payload)
                                            yield payload
                                    except Exception:
                                        pass  # Skip if malformed

                                    buffer = buffer[end_idx + 1:]
                                else:
                                    break

            # ── Save batch to Mem0 after full stream ─────────────────────
            await self._save_to_memory(
                user_query=user_input,
                cards=generated_cards,
                user_id=user_id,
            )

        except Exception as e:
            yield {"type": "error", "content": str(e)}

    # ── Mem0 Recall ────────────────────────────────────────────────────────

    async def recall_ui_content(
        self, agent_response: str, user_id: str
    ) -> Optional[list[dict]]:
        """
        Search Mem0 for the most relevant previously-shown flashcard batch for
        this user. Returns the list of card payloads if found, otherwise None.
        """
        if not user_id:
            self.logger.warning("⚠️ recall_ui_content called with no user_id")
            return None

        self.logger.info(
            "🔍 Recalling UI content from Mem0 for: '%s' (user: %s)",
            agent_response,
            user_id,
        )

        try:
            results = self.memory.search(query=agent_response, user_id=user_id, limit=1)

            if not results or not results.get("results"):
                self.logger.info("🔍 No Mem0 results found for: %s", agent_response)
                return None

            top_result = results["results"][0]
            metadata = top_result.get("metadata", {})

            # Retrieve cards from metadata if present (new format)
            if "cards" in metadata:
                try:
                    cards = json.loads(metadata["cards"])
                    self.logger.info(
                        "✅ Recalled %d flashcard(s) from Mem0 metadata for user %s",
                        len(cards),
                        user_id,
                    )
                    return cards
                except Exception as e:
                    self.logger.error("❌ Failed to parse cards from Mem0 metadata: %s", e)

            # Fallback to old format: The memory field contains our stored JSON string
            memory_text: str = top_result.get("memory", "")
            if not memory_text:
                return None

            # Memory text was stored as: "user_query: ... | cards: [...]"
            if "| cards: " in memory_text:
                cards_json_str = memory_text.split("| cards: ", 1)[1]
                cards = json.loads(cards_json_str)
                self.logger.info(
                    "✅ Recalled %d flashcard(s) from legacy Mem0 text for user %s",
                    len(cards),
                    user_id,
                )
                return cards

            return None

        except Exception as e:
            self.logger.error("❌ Mem0 recall failed: %s", e)
            return None

    # ── Private Helpers ────────────────────────────────────────────────────

    async def _save_to_memory(
        self,
        user_query: str,
        cards: list[dict],
        user_id: str | None,
    ) -> None:
        """Persist the flashcard batch to Mem0 for later recall."""
        if not user_id:
            self.logger.info("⚠️ Skipping Mem0 save — no user_id (guest session)")
            return

        if not cards:
            self.logger.info("⚠️ Skipping Mem0 save — no cards generated")
            return

        try:
            cards_json = json.dumps(cards)
            # Use a more "factual" content for Mem0 to ensure it extracts and saves the memory.
            # We store the actual payloads in metadata for reliability.
            memory_content = f"The user viewed flashcards for the query: '{user_query}'."

            self.memory.add(
                messages=[{"role": "user", "content": memory_content}],
                user_id=user_id,
                metadata={
                    "topic": "ui_flashcard",
                    "user_query": user_query,
                    "cards": cards_json
                },
            )

            self.logger.info(
                "✅ Saved %d flashcard(s) to Mem0 metadata for user %s (query: '%s')",
                len(cards),
                user_id,
                user_query,
            )
        except Exception as e:
            self.logger.error("❌ Mem0 save failed: %s", e)

    async def _normalize_card_payload(self, card_obj: dict) -> dict | None:
        if not isinstance(card_obj, dict):
            return None

        payload: dict[str, Any] = {"type": "flashcard"}

        # Include id for deduplication tracking
        for key in (
            "id",
            "title",
            "value",
            "visual_intent",
            "animation_style",
            "icon",
            "media",
            "accentColor",
            "theme",
            "size",
            "layout",
            "image",
        ):
            if key in card_obj and card_obj[key] is not None:
                payload[key] = card_obj[key]

        if "visual_intent" not in payload and "intent" in card_obj:
            payload["visual_intent"] = card_obj["intent"]

        if "animation_style" not in payload and "animation" in card_obj:
            payload["animation_style"] = card_obj["animation"]

        if "accent_color" in card_obj and "accentColor" not in payload:
            payload["accentColor"] = card_obj["accent_color"]

        if (
            "image_url" in card_obj
            or "image_alt" in card_obj
            or "image_aspect_ratio" in card_obj
        ):
            payload.setdefault("image", {})
            image = payload["image"] if isinstance(payload["image"], dict) else {}
            if "image_url" in card_obj:
                image["url"] = card_obj["image_url"]
            if "image_alt" in card_obj:
                image["alt"] = card_obj["image_alt"]
            if "image_aspect_ratio" in card_obj:
                image["aspectRatio"] = card_obj["image_aspect_ratio"]
            payload["image"] = image

        if "title" not in payload or "value" not in payload:
            return None

        return payload

    # ── Update Instructions ────────────────────────────────────────────────

    async def update_instructions_with_context(self, ui_context: dict) -> None:
        self.logger.info("Updating instructions with UI context")
        md = []
        for key, value in ui_context.items():
            md.append(
                f"**{key}**: `{json.dumps(value, indent=2, default=str) if isinstance(value, (dict, list)) else value}`"
            )

        self.instructions = (
            UI_SYSTEM_INSTRUCTION
            + "\n\nThe following is the current UI state. Generate the visual accordingly:\n\n"
            + "\n".join(md)
        )