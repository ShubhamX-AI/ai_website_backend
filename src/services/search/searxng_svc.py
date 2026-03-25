import time
from typing import Any

import httpx

from src.core.config import settings

DEFAULT_BASE_URL = settings.SEARXNG_BASE_URL
DEFAULT_LIMIT = 10
DEFAULT_TIMEOUT = 10.0


class SearXNGService:
    """Async SearXNG client for internet search."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        default_limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_limit = default_limit

    @staticmethod
    def _error_payload(message: str, query: str, source: str) -> dict[str, Any]:
        return {"error": True, "message": message, "query": query, "source": source}

    @staticmethod
    def _fmt_http_error(exc: httpx.HTTPError) -> str:
        detail = str(exc).strip() or repr(exc)
        return f"{exc.__class__.__name__}: {detail}"

    async def _get_json(
        self,
        url: str,
        params: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def search_info(
        self,
        query: str,
        limit: int = DEFAULT_LIMIT,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """General web search -> {title, url, snippet, engine}."""
        q = query.strip()
        source = base_url.rstrip("/") or self.base_url
        result_limit = limit or self.default_limit
        call_timeout = timeout or self.timeout

        if not q:
            return self._error_payload("empty query", q, source)
        if result_limit <= 0:
            return self._error_payload("limit must be > 0", q, source)

        t0 = time.perf_counter()
        try:
            data = await self._get_json(
                f"{source}/search",
                {"q": q, "format": "json"},
                call_timeout,
            )
        except httpx.HTTPError as exc:
            return self._error_payload(
                f"request failed: {self._fmt_http_error(exc)}", q, source
            )
        except ValueError as exc:
            return self._error_payload(f"bad JSON: {exc}", q, source)

        results = [
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("content") or "",
                "engine": item.get("engine") or "",
            }
            for item in data.get("results", [])[:result_limit]
        ]

        return {
            "query": q,
            "count": len(results),
            "results": results,
            "took_ms": round((time.perf_counter() - t0) * 1000, 2),
            "source": source,
            "error": False,
        }

    async def search_images(
        self,
        query: str,
        limit: int = 3,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> list[str]:
        """Search SearXNG for images and return a list of image URLs."""
        q = query.strip()
        if not q:
            return []

        call_timeout = timeout or self.timeout
        try:
            data = await self._get_json(
                f"{self.base_url}/search",
                {"q": q, "format": "json", "categories": "images"},
                call_timeout,
            )
        except (httpx.HTTPError, ValueError):
            return []

        # Extract image URLs: prefer img_src, fall back to thumbnail
        urls: list[str] = []
        for item in data.get("results", []):
            url = item.get("img_src") or item.get("thumbnail") or ""
            if url:
                urls.append(url)
            if len(urls) >= limit:
                break

        return urls

    @staticmethod
    def preprocess_for_llm(search_result: dict[str, Any], min_snippet_len: int = 40) -> str:
        """Strip low-value snippets and return compact plaintext for LLM."""
        results = search_result.get("results", [])
        lines = []

        for i, result in enumerate(results, 1):
            snippet = (result.get("snippet") or "").strip()
            if len(snippet) < min_snippet_len:
                continue

            if len(snippet) > 500:
                snippet = snippet[:500].rsplit(" ", 1)[0] + "..."

            title = result.get("title") or ""
            lines.append(f"[{i}] {title}\n    {snippet}")

        return "\n\n".join(lines) if lines else "No useful snippets found."
