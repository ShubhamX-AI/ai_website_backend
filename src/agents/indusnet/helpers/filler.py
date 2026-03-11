import logging
from collections import deque
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Isolated client — never touches the agent's realtime session
_client = AsyncOpenAI()

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
        response = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI agent on a live voice call, actively listening while the user speaks.\n"
                        "Your ONLY job: output a single short filler phrase (1-4 words) that fits the emotional "
                        "tone of the recent conversation.\n\n"
                        "Rules:\n"
                        "- Match the tone: serious/hard topics → 'I understand.', 'I see.', 'That's tough.'; "
                        "excited topics → 'Oh wow!', 'Really?!'; neutral → 'Mm-hmm.', 'Right.', 'Go on.'\n"
                        "- NEVER answer, advise, or continue the conversation.\n"
                        "- NEVER output more than 4 words.\n"
                        "- No quotes. Only natural punctuation.\n"
                        f"{avoid_clause}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"{context_block}The user is currently speaking. Output only the filler phrase.",
                },
            ],
            max_tokens=10,
            temperature=0.95,
        )
        text = response.choices[0].message.content.strip()
        _recent_fillers.append(text)
        logger.debug(f"[filler] generated: {text!r}")
        return text
    except Exception as e:
        logger.warning(f"[filler] generation failed (skipping): {e}")
        return None
