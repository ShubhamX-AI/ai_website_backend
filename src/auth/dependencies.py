import json
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from src.auth.jwt import verify_token


def get_current_user(auth_session: Annotated[str | None, Cookie()] = None) -> dict:
    if not auth_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        token = json.loads(auth_session).get("token")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    return verify_token(token)  # {"sub": email, "role": role}


def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
