import logging
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Optional
from src.services.livekit.livekit_svc import livekit_service

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_AGENTS = {"indusnet"}

@router.get("/getToken", response_class=PlainTextResponse)
async def get_token(
    name: str = Query("guest"), 
    agent: str = Query("web"), 
    room: Optional[str] = Query(None)
):
    if agent not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail="Invalid agent")
    
    if not room:
        room = await livekit_service.generate_room_name(agent=agent)

    try:
        jwt = livekit_service.get_token(name, agent, room)
        logger.info(f"JWT issued | room={room} | agent={agent}")
        return jwt
    except Exception as e:
        logger.error(f"Error generating JWT: {e}")
        raise HTTPException(status_code=500, detail="Error generating token.")
