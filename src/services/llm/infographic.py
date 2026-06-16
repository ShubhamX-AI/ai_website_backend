"""
Infographic card schema — the single text-led card type.

Two visual card types reach the frontend: image "flashcard" and composed text
"infographic". An infographic is an optional hero plus an ordered list of typed
section blocks. This module is the one place that builds and validates that
shape, so the LLM-generated path (ui_agent) and the agent-authored path
(publish_infographic) emit identical payloads.
"""
from typing import Any

# The only section "type" values the frontend renders. Anything else is dropped.
ALLOWED_BLOCKS = ("markdown", "bullet_list", "icon_bullets", "stats", "cta_banner")

# The only preset graphic keys the frontend can render. Any other value (an invented
# key, a URL, inline SVG) renders nothing on the client, so we strip it here to keep
# payloads clean. Keep this in sync with PRESET GRAPHIC KEYS in prompts.py.
ALLOWED_GRAPHICS = frozenset((
    "devops_loop", "cicd_pipeline", "cloud_stack", "ai_workflow", "security_shield",
    "growth_chart", "web_development", "data_analytics", "team_collaboration",
    "digital_marketing",
))


def _clean_graphic(value: Any) -> str:
    """Return the graphic key only if it is an allowed preset; else empty string."""
    key = _clean_str(value)
    return key if key in ALLOWED_GRAPHICS else ""

_DEFAULT_INTENT = "neutral"
_DEFAULT_ICON = "info"


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_str_list(values: Any) -> list[str]:
    return [s for s in (_clean_str(v) for v in values or []) if s]


def _normalize_section(block: Any) -> dict | None:
    """Validate one section block; return a clean copy or None if unusable."""
    if not isinstance(block, dict):
        return None

    btype = block.get("type")
    if btype not in ALLOWED_BLOCKS:
        return None  # closed enum — defense in depth against a stray LLM type

    section: dict[str, Any] = {"type": btype}
    title = _clean_str(block.get("title"))
    if title:
        section["title"] = title

    if btype == "markdown":
        content = _clean_str(block.get("content") or block.get("value"))
        if not content:
            return None
        section["content"] = content

    elif btype == "bullet_list":
        items = _clean_str_list(block.get("items"))
        if not items:
            return None
        section["items"] = items

    elif btype == "icon_bullets":
        items = []
        for it in block.get("items") or []:
            if not isinstance(it, dict):
                continue
            text = _clean_str(it.get("text") or it.get("title"))
            if not text:
                continue
            items.append({
                "icon": _clean_str(it.get("icon")) or _DEFAULT_ICON,
                "title": _clean_str(it.get("title")),
                "text": text,
            })
        if not items:
            return None
        graphic = _clean_graphic(block.get("graphic"))
        if graphic:
            section["graphic"] = graphic
        section["items"] = items

    elif btype == "stats":
        items = []
        for it in block.get("items") or []:
            if not isinstance(it, dict):
                continue
            value = _clean_str(it.get("value"))
            label = _clean_str(it.get("label"))
            if not value or not label:
                continue
            items.append({
                "icon": _clean_str(it.get("icon")) or _DEFAULT_ICON,
                "value": value,
                "label": label,
                "intent": _clean_str(it.get("intent")) or _DEFAULT_INTENT,
            })
        if not items:
            return None
        section["items"] = items

    elif btype == "cta_banner":
        if not title:  # title is required for this block; set above if present
            return None
        section["text"] = _clean_str(block.get("text"))
        section["icon"] = _clean_str(block.get("icon")) or _DEFAULT_ICON

    return section


def _normalize_hero(hero: Any) -> dict | None:
    if not isinstance(hero, dict):
        return None
    title = _clean_str(hero.get("title"))
    if not title:
        return None
    out: dict[str, Any] = {"title": title}
    desc = _clean_str(hero.get("description"))
    if desc:
        out["description"] = desc
    out["icon"] = _clean_str(hero.get("icon")) or _DEFAULT_ICON
    graphic = _clean_graphic(hero.get("graphic"))
    if graphic:
        out["graphic"] = graphic
    return out


def normalize_infographic_payload(card_obj: dict) -> dict | None:
    """Validate an infographic card (from the LLM or a tool) into a clean payload.

    Returns None when the card carries no renderable content (no hero and no
    usable section). Unknown section types are dropped silently.
    """
    if not isinstance(card_obj, dict):
        return None

    hero = _normalize_hero(card_obj.get("hero"))
    sections = [
        s for s in (_normalize_section(b) for b in card_obj.get("sections") or [])
        if s is not None
    ]

    # Legacy/simple shape: a flat "content"/"value" + "bullets" with no sections.
    if not sections:
        content = _clean_str(card_obj.get("content") or card_obj.get("value"))
        if content:
            sections.append({"type": "markdown", "content": content})
        bullets = _clean_str_list(card_obj.get("bullets"))
        if bullets:
            sections.append({"type": "bullet_list", "items": bullets})

    if not hero and not sections:
        return None

    payload: dict[str, Any] = {
        "type": "infographic",
        "title": _clean_str(card_obj.get("title")) or (hero["title"] if hero else ""),
        "visual_intent": _clean_str(card_obj.get("visual_intent"))
        or _clean_str(card_obj.get("intent"))
        or _DEFAULT_INTENT,
        "icon": _clean_str(card_obj.get("icon")) or _DEFAULT_ICON,
        "sections": sections,
    }
    if hero:
        payload["hero"] = hero
    chips = _clean_str_list(card_obj.get("chips"))
    if chips:
        payload["chips"] = chips
    if card_obj.get("id") is not None:
        payload["id"] = card_obj["id"]
    return payload


def build_simple_infographic(
    title: str,
    markdown_content: str,
    bullets: list[str] | None = None,
    chips: list[str] | None = None,
    visual_intent: str = _DEFAULT_INTENT,
    icon: str = _DEFAULT_ICON,
) -> dict:
    """Build an infographic from the simple agent-authored arguments.

    Produces a hero (title + header icon) plus a markdown section and an optional
    bullet_list — the minimal composition that renders identically to a rich LLM
    infographic. Falls back to a bare title if no body was supplied.
    """
    return normalize_infographic_payload({
        "title": title,
        "visual_intent": visual_intent,
        "icon": icon,
        "hero": {"icon": icon, "title": title},
        "content": markdown_content,
        "bullets": bullets or [],
        "chips": chips or [],
    })
