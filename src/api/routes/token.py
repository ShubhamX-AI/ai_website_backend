import logging
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import PlainTextResponse
from typing import Optional
from src.services.livekit.livekit_svc import LiveKitService

logger = logging.getLogger(__name__)
router = APIRouter()
livekit_service = LiveKitService()
ALLOWED_AGENTS = {"indusnet"}

@router.get("/getToken", response_class=PlainTextResponse)
async def get_token(
    name: str = Query("guest"), 
    user_id: str = Query(..., description="Persistent UUID for the user"),
    email: Optional[str] = Query(None),
    agent: str = Query("indusnet"), 
    room: Optional[str] = Query(None)
):
    if agent not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail="Invalid agent")
    
    if not room:
        room = await livekit_service.create_room(agent=agent)
    
    await livekit_service.create_agent_dispatch(room_name=room)

    try:
        # Pass user_id as the identity, and handle name/email in metadata or name field
        jwt = livekit_service.get_token(identity=user_id, name=name, agent=agent, room=room, email=email)
        logger.info(f"JWT issued | room={room} | agent={agent} | user_id={user_id} | name={name}")
        return jwt
    except Exception as e:
        logger.error(f"Error generating JWT: {e}")
        raise HTTPException(status_code=500, detail="Error generating token.")
