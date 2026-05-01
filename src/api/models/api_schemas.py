from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    role: str
    expires_at: int | None  # ms epoch; None for admin


class LogoutResponse(BaseModel):
    success: bool
