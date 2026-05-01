from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status
from src.core.config import settings

_ALGORITHM = "HS256"
_ADMIN_EXPIRY_DAYS = 30
_CLIENT_EXPIRY_HOURS = settings.CLIENT_SESSION_HOURS


def create_token(email: str, role: str) -> tuple[str, int | None]:
    """Return (signed_jwt, expires_at_ms). expires_at_ms is None for admin."""
    now = datetime.now(timezone.utc)

    if role == "client":
        exp = now + timedelta(hours=_CLIENT_EXPIRY_HOURS)
        expires_at_ms: int | None = int(exp.timestamp() * 1000)
    else:
        exp = now + timedelta(days=_ADMIN_EXPIRY_DAYS)
        expires_at_ms = None

    payload = {"sub": email, "role": role, "exp": exp, "iat": now}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)
    return token, expires_at_ms


def verify_token(token: str) -> dict:
    """Decode and validate JWT. Raises 401 on any failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
