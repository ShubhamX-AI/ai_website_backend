from pydantic import BaseModel, Field
from typing import Optional, List

# --- UI / Flashcard Models (Migrated from agent logic) ---

class FlashcardImage(BaseModel):
    url: Optional[str] = None
    alt: Optional[str] = None
    aspectRatio: Optional[str] = None

class SmartIcon(BaseModel):
    type: str = "static"  # "static" | "animated"
    ref: str
    fallback: Optional[str] = "info"

class DynamicMedia(BaseModel):
    urls: Optional[List[str]] = None
    query: Optional[str] = None
    source: Optional[str] = "unsplash"
    aspectRatio: Optional[str] = "auto"
    mediaType: Optional[str] = "image"

class Flashcard(BaseModel):
    type: str = "flashcard"
    id: Optional[str] = None
    title: str
    value: str
    visual_intent: Optional[str] = "neutral"
    animation_style: Optional[str] = "pop"
    icon: Optional[SmartIcon | str] = None
    media: Optional[DynamicMedia] = None
    accentColor: Optional[str] = None
    theme: Optional[str] = None
    size: Optional[str] = "md"
    layout: Optional[str] = "default"
    image: Optional[FlashcardImage] = None

class UIStreamResponse(BaseModel):
    cards: List[Flashcard] = Field(default_factory=list)
