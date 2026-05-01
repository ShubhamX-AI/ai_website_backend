import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from passlib.hash import bcrypt

from src.api.models.api_schemas import LoginRequest, LogoutResponse, TokenResponse
from src.api.models.db_schemas import User
from src.auth.jwt import create_token
from src.core.config import settings
from src.core.database import get_database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    db = get_database()
    doc = await db["users"].find_one({"email": body.email})

    if not doc or not doc.get("hashed_password") or not bcrypt.verify(body.password, doc["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    now = datetime.now(timezone.utc)

    # Enforce access window for clients (Option B: window from first login)
    if doc["role"] == "client":
        first_login_at = doc.get("first_login_at")
        if first_login_at is None:
            # First ever login — stamp it
            await db["users"].update_one({"email": doc["email"]}, {"$set": {"first_login_at": now}})
            first_login_at = now
        else:
            if isinstance(first_login_at, datetime) and first_login_at.tzinfo is None:
                first_login_at = first_login_at.replace(tzinfo=timezone.utc)
            deadline = first_login_at + timedelta(hours=settings.CLIENT_ACCESS_WINDOW_HOURS)
            if now > deadline:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access window expired")

    token, expires_at = create_token(doc["email"], doc["role"])
    logger.info("login success | email=%s role=%s", doc["email"], doc["role"])
    return TokenResponse(token=token, role=doc["role"], expires_at=expires_at)


@router.get("/google")
async def google_login() -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth not configured")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(code: str = Query(...)) -> RedirectResponse:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth not configured")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token exchange failed")

        access_token = token_resp.json().get("access_token")

        userinfo_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch Google user info")

        userinfo = userinfo_resp.json()

    email: str = userinfo.get("email", "")
    google_id: str = userinfo.get("sub", "")

    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account has no email")

    db = get_database()
    doc = await db["users"].find_one({"email": email})

    if doc is None:
        domain = email.split("@")[-1]
        role = "admin" if domain == settings.ADMIN_DOMAIN else "client"
        await db["users"].insert_one(User(email=email, google_id=google_id, role=role).model_dump())
        logger.info("new Google user | email=%s role=%s", email, role)
    else:
        role = doc["role"]
        if doc.get("google_id") != google_id:
            await db["users"].update_one({"email": email}, {"$set": {"google_id": google_id}})

    token, expires_at = create_token(email, role)
    logger.info("Google login success | email=%s role=%s", email, role)

    query = urlencode({
        "token": token,
        "role": role,
        "expires_at": "" if expires_at is None else str(expires_at),
    })
    return RedirectResponse(url=f"{settings.NEXTJS_CALLBACK_URL}?{query}")


@router.post("/logout", response_model=LogoutResponse)
async def logout() -> LogoutResponse:
    return LogoutResponse(success=True)
