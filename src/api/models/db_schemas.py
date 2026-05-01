from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    email: EmailStr
    hashed_password: str | None = None
    role: str = "client"
    google_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    first_login_at: datetime | None = None
