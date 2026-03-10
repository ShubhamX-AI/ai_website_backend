"""
Shared async LLM formatting utility.

Both email and WhatsApp need to turn a UI snapshot into structured text.
This module owns that responsibility once — callers just pass a system prompt
and get back a parsed result or None.
"""
import logging
from typing import TypeVar, Type

from openai import AsyncOpenAI
from pydantic import BaseModel

from src.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def llm_parse(
    snapshot: dict,
    system_prompt: str,
    response_model: Type[T],
) -> T | None:
    """
    Ask the LLM to parse a snapshot into a typed Pydantic model.

    Returns None if OpenAI is not configured or the call fails,
    so callers can fall back gracefully.
    """
    if not settings.OPENAI_API_KEY:
        return None

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=8.0)
        response = await client.beta.chat.completions.parse(
            model=settings.EMAIL_SUMMARY_MODEL,
            temperature=0.2,
            response_format=response_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(snapshot)},
            ],
        )
        return response.choices[0].message.parsed
    except Exception as exc:
        logger.error("LLM formatting failed: %s", exc)
        return None


async def llm_text(
    snapshot: dict,
    system_prompt: str,
) -> str | None:
    """
    Ask the LLM to produce a plain-text string from a snapshot.

    Returns None if OpenAI is not configured or the call fails.
    """
    if not settings.OPENAI_API_KEY:
        return None

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=8.0)
        response = await client.chat.completions.create(
            model=settings.EMAIL_SUMMARY_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(snapshot)},
            ],
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception as exc:
        logger.error("LLM text formatting failed: %s", exc)
        return None
