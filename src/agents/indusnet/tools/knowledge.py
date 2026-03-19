from livekit.agents import function_tool, RunContext


class KnowledgeToolsMixin:
    """Tooling for KB search and direct internet search."""

    @function_tool
    async def search_indus_net_knowledge_base(self, context: RunContext, question: str):
        """Search the official Indus Net Knowledge Base for information about the company."""
        self.logger.info(f"Searching knowledge base for: {question}")
        # Await the search to ensure db_results is populated before returning
        await self._vector_db_search(question)
        return self.db_results

    @function_tool
    async def search_internet_knowledge(self, context: RunContext, question: str):
        """Search the internet using SearXNG and return cleaned snippets for LLM use."""
        self.logger.info(f"Searching internet for: {question}")

        payload = await self.search_service.search_info(question)
        if payload.get("error"):
            message = payload.get("message", "Internet search failed")
            return f"Internet search failed: {message}"

        cleaned = self.search_service.preprocess_for_llm(payload)
        return cleaned
