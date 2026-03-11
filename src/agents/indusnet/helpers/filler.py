import logging
from collections import deque
from src.core.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Rolling window of recent fillers to prevent repetition
_recent_fillers: deque[str] = deque(maxlen=5)


async def generate_filler(context: list[dict]) -> str | None:
    """Ask a small LLM for a short filler phrase matching the conversation tone.

    Uses a standalone client so the agent's main ChatContext is never touched.
    context: recent completed turns as [{"role": "user"|"assistant", "text": "..."}].
    Returns None on any error so callers can safely skip the filler.
    """
    avoid = list(_recent_fillers)
    avoid_clause = f"Do NOT use any of: {avoid}. " if avoid else ""

    # Build a compact context block from the last few turns
    if context:
        ctx_lines = "\n".join(
            f"{i + 1}. [{t['role'].capitalize()}]: {t['text']}"
            for i, t in enumerate(context[-4:])
        )
        context_block = f"Recent conversation:\n{ctx_lines}\n\n"
    else:
        context_block = ""

    try:
        # Isolated client — never touches the agent's realtime session
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = await _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a human listener on a live voice call. The user is mid-sentence RIGHT NOW — "
                    "they haven't finished speaking.\n\n"
                    "Your ONLY job: produce a single backchannel filler (1–3 words) that a human would "
                    "murmur WHILE the other person is still talking — not after.\n\n"
                    "CRITICAL RULES:\n"
                    "- The filler must feel natural MID-SENTENCE, not as a response to a complete thought.\n"
                    "- Prefer ultra-short: 'Mm.', 'Yeah.', 'Mm-hmm.', 'Right.', 'Uh-huh.' for neutral flow.\n"
                    "- Tone-match only if the emotional signal is very strong:\n"
                    "    sad/heavy → 'Mm.', 'Yeah...', 'I see.'\n"
                    "    excited/surprising → 'Oh!', 'Wow.', 'Really?'\n"
                    "    thoughtful/explaining → 'Right.', 'Mm-hmm.', 'Yeah.'\n"
                    "- NEVER complete their thought, answer, advise, or ask anything.\n"
                    "- NEVER use more than 3 words.\n"
                    "- No quotes. Natural punctuation only.\n"
                    "- Default to the shortest possible filler. When in doubt: 'Mm-hmm.' or 'Yeah.'\n"
                    f"{avoid_clause}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{context_block}"
                    "The user is still speaking mid-sentence. "
                    "Output only the filler word or phrase a human listener would murmur right now."
                ),
            },
        ],
        max_tokens=10,
        temperature=0.9,
    )
        text = response.choices[0].message.content.strip()
        _recent_fillers.append(text)
        logger.debug(f"[filler] generated: {text!r}")
        return text
    except Exception as e:
        logger.warning(f"[filler] generation failed (skipping): {e}")
        return None
