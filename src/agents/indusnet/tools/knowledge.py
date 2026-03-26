import asyncio
import re

from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import TOPIC_UI_FLASHCARD

# Conversational fluff that degrades search quality
_FLUFF_PATTERN = re.compile(
    r"^(can you|could you|please|tell me about|what about|what is|what are|"
    r"who is|show me|explain|i want to know|let me know|give me|do you know)\s+",
    re.IGNORECASE,
)


def _enrich_query(raw_query: str) -> str:
    """Strip conversational fluff and ensure query has enough context for a search engine."""
    q = raw_query.strip()
    # Remove leading filler words
    q = _FLUFF_PATTERN.sub("", q).strip(" ?!.,:")
    # If the query is too short after cleanup, keep the original
    if len(q) < 5:
        q = raw_query.strip()
    return q


class KnowledgeToolsMixin:
    """Tooling for KB search and direct internet search."""

    @function_tool
    async def search_indus_net_knowledge_base(self, context: RunContext, question: str):
        """Search the official Indus Net Knowledge Base for information about the company."""
        self.logger.info(f"Searching knowledge base for: {question}")
        await self._vector_db_search(question)
        return self.db_results

    @function_tool
    async def search_internet_knowledge(self, context: RunContext, question: str):
        """Search the internet using SearXNG and return cleaned snippets for LLM use."""
        # Clean up vague conversational fragments into proper search queries
        enriched_q = _enrich_query(question)
        self.logger.info(f"Searching internet for: {enriched_q} (raw: {question})")

        general, news, it_results = await asyncio.gather(
            self.search_service.search_info(enriched_q),
            self.search_service.search_news(enriched_q),
            self.search_service.search_it(enriched_q),
            return_exceptions=True,
        )

        # Build merged, deduplicated text for the LLM
        sections: list[str] = []

        # General results
        if isinstance(general, dict) and not general.get("error"):
            text = self.search_service.preprocess_for_llm(general)
            if text and text != "No useful snippets found.":
                sections.append(f"[General]\n{text}")

        # News results (with dates)
        if isinstance(news, list) and news:
            text = self.search_service.preprocess_news_for_llm(news)
            if text and text != "No news found.":
                sections.append(f"[News]\n{text}")

        # IT / tech results
        if isinstance(it_results, list) and it_results:
            # Wrap list into a dict compatible with preprocess_for_llm
            it_payload = {"results": [
                {"title": r["title"], "snippet": r["snippet"]} for r in it_results
            ]}
            text = self.search_service.preprocess_for_llm(it_payload)
            if text and text != "No useful snippets found.":
                sections.append(f"[Tech / IT]\n{text}")

        if not sections:
            return "Internet search returned no useful results."

        return "\n\n".join(sections)
