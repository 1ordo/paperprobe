"""Base agent class for all COSMIN AI agents."""
import logging
from typing import Callable

from app.services.ai_client import AIClient
from app.services.vector_store import VectorStore
from app.config import settings

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class providing shared infrastructure for all agents."""

    def __init__(
        self,
        paper_id: str,
        ai_client: AIClient | None = None,
        vector_store: VectorStore | None = None,
        model: str | None = None,
    ):
        self.paper_id = paper_id
        self.ai_client = ai_client or AIClient()
        self.vector_store = vector_store or VectorStore()
        self.model = model

    async def retrieve_context(self, query: str, limit: int = 10) -> list[dict]:
        """Retrieve relevant document chunks via semantic search."""
        embedding = await self.ai_client.create_embedding(query)
        results = self.vector_store.search(
            query_embedding=embedding,
            paper_id=self.paper_id,
            limit=limit,
        )
        return results

    async def retrieve_multi_context(self, queries: list[str], limit_per_query: int = 5) -> list[dict]:
        """Retrieve context for multiple queries, deduplicated by chunk ID."""
        seen_ids = set()
        all_results = []
        for query in queries:
            results = await self.retrieve_context(query, limit=limit_per_query)
            for r in results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    all_results.append(r)
        # Sort by score descending
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results

    def format_context(self, chunks: list[dict], max_chars: int = 8000) -> str:
        """Format retrieved chunks into a context string for the LLM."""
        parts = []
        total = 0
        for chunk in chunks:
            text = chunk["text"]
            page = chunk.get("page_number", "?")
            prefix = f"[Page {page}] "
            entry = prefix + text
            if total + len(entry) > max_chars:
                break
            parts.append(entry)
            total += len(entry)
        return "\n\n---\n\n".join(parts)

    async def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str | dict:
        """Call the LLM with system and user prompts."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        model = model or self.model
        kwargs = {"model": model}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if json_mode:
            return await self.ai_client.chat_completion_json(messages, **kwargs)
        return await self.ai_client.chat_completion(messages, **kwargs)
