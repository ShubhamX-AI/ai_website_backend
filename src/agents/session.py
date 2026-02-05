import logging
import json
import asyncio
import os
from typing import cast
from livekit import rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    BackgroundAudioPlayer,
    AudioConfig,
)
from livekit.plugins import cartesia
from livekit.plugins.openai import realtime
from openai.types.realtime import AudioTranscription
from openai.types.beta.realtime.session import TurnDetection

from src.core.config import settings
from src.core.logger import setup_logging
from src.agents.factory import get_agent_class
from src.agents.indusnet.agent import IndusNetAgent

setup_logging()
logger = logging.getLogger(__name__)

server = AgentServer(
    api_key=settings.LIVEKIT_API_KEY,
    api_secret=settings.LIVEKIT_API_SECRET,
    ws_url=settings.LIVEKIT_URL,
    job_memory_warn_mb=1024
)

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        llm=realtime.RealtimeModel(
            model="gpt-realtime",
            input_audio_transcription=AudioTranscription(
                model="gpt-4o-mini-transcribe",
                prompt="Transcribe exactly what is spoken."
            ),
            input_audio_noise_reduction="near_field",
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="low",
                create_response=True,
                interrupt_response=True,
            ),
            modalities=["text"],
            api_key=cast(str, settings.OPENAI_API_KEY),
        ),
        tts=cartesia.TTS(
            model="sonic-3",
            voice="faf0731e-dfb9-4cfc-8119-259a79b27e12",
            api_key=settings.CARTESIA_API_KEY,
        ),
        preemptive_generation=True,
    )

    # Background audio
    ambient_path = os.path.join(settings.AUDIO_DIR, "office-ambience_48k.wav")
    typing_path = os.path.join(settings.AUDIO_DIR, "typing-sound_48k.wav")
    
    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(ambient_path, volume=0.4),
        thinking_sound=AudioConfig(typing_path, volume=0.5),
    )

    await session.start(
        agent=IndusNetAgent(room=ctx.room),
        room=ctx.room
        )
    
    participant = await ctx.wait_for_participant()
    
    # Extract User Identity & Context
    user_id = participant.identity
    user_name = participant.name or "Guest"
    user_email = None
    agent_type = "indusnet"
    
    try:
        metadata = json.loads(participant.metadata or "{}")
        agent_type = metadata.get("agent", "indusnet")
        user_email = metadata.get("user_email")
    except Exception as e:
        logger.warning(f"Failed to parse participant metadata: {e}")

    logger.info(f"User Connected | ID: {user_id} | Name: {user_name} | Email: {user_email}")

    AgentClass = get_agent_class(agent_type)
    # TODO: Update AgentClass to accept user_id, user_name on init for cleaner DI
    agent_instance = AgentClass(room=ctx.room) 
    
    # # HACK: Manually set user context on the agent instance for now
    # if hasattr(agent_instance, "set_user_context"):
    #     agent_instance.set_user_context(user_id, user_name, user_email)

    session.update_agent(agent=agent_instance)

    # Register data handler for UI context sync and other room events
    ctx.room.on("data_received", agent_instance.handle_data)

    # Start background audio
    asyncio.create_task(background_audio.start(room=ctx.room, agent_session=session))
         
    await session.generate_reply(instructions="Greet the user professional yet friendly in english.")

    # Keep alive
    participant_left = asyncio.Event()
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        if p.identity == participant.identity:
            participant_left.set()

    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED and not participant_left.is_set():
        await asyncio.sleep(1)

if __name__ == "__main__":
    cli.run_app(server)
