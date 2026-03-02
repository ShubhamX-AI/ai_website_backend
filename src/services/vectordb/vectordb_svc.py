import logging
import asyncio
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from src.core.config import settings

logger = logging.getLogger(__name__)

class VectorStoreService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY
        )
        self.vectorstore = Chroma(
            persist_directory=f"{settings.BASE_DIR}/src/services/vectordb/chroma_db",
            embedding_function=self.embeddings,
            collection_name="company_knowledge"
        )

    async def search(self, query: str, k: int = 5):
        # Run synchronous Chroma search in a thread
        results = await asyncio.to_thread(
            self.vectorstore.similarity_search, 
            query=query, 
            k=k
        )
        return results


# Remove the global instance to avoid issues during Docker build when API keys are not present
# vector_store = VectorStoreService()
