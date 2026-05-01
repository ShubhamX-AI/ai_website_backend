from typing import Literal

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    admin_email: EmailStr
    admin_password: str
    email: EmailStr
    password: str
    role: Literal["admin", "client"] = "client"


class TokenResponse(BaseModel):
    token: str
    role: str
    expires_at: int | None  # ms epoch; None for admin


class LogoutResponse(BaseModel):
    success: bool
