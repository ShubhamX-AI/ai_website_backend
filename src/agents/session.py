import logging
import json
import asyncio
import os
from typing import cast
from livekit import rtc
from livekit.agents import (
    WorkerOptions,
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    BackgroundAudioPlayer,
    AudioConfig,
    room_io,
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


async def entrypoint(ctx: JobContext):
    session = AgentSession(
        llm=realtime.RealtimeModel(
            model="gpt-realtime",
            input_audio_transcription=AudioTranscription(
                model="gpt-4o-mini-transcribe",
                prompt="Transcribe exactly what is spoken. If not understood ask the user to please repeat",
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
        use_tts_aligned_transcript=True,
    )

    # Background audio
    ambient_path = os.path.join(settings.AUDIO_DIR, "office-ambience_48k.wav")
    typing_path = os.path.join(settings.AUDIO_DIR, "typing-sound_48k.wav")

    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(ambient_path, volume=0.4),
        thinking_sound=AudioConfig(typing_path, volume=0.5),
    )

    agent_instance = IndusNetAgent(room=ctx.room)

    # Configure room options
    room_options = room_io.RoomOptions(
        text_input=True,
        audio_input=True,
        audio_output=True,
        close_on_disconnect=True,
        delete_room_on_close=True,
    )

    await session.start(agent=agent_instance, room=ctx.room, room_options=room_options)

    participant = await ctx.wait_for_participant()
    logger.info(
        f"User Connected | Identity: {participant.identity} | Name: {participant.name} | Metadata: {participant.metadata}"
    )

    # Register data handler for UI context sync and other room events
    ctx.room.on("data_received", agent_instance.handle_data)

    # Start background audio
    asyncio.create_task(background_audio.start(room=ctx.room, agent_session=session))

    # Greet the participant
    if participant.name:
        logger.info(f"Greeting user with name: {participant.name}")
        await session.generate_reply(
            instructions=f"Greet the user - **{participant.name}** professionally and friendly using their first name. Welcome them back to the website in English."
        )
    else:
        logger.info("Greeting user without name")
        await session.generate_reply(
            instructions="Greet the user in a professional and friendly manner in English."
        )

    # Keep alive
    participant_left = asyncio.Event()

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        if p.identity == participant.identity:
            participant_left.set()

    while (
        ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED
        and not participant_left.is_set()
    ):
        await asyncio.sleep(1)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            ws_url=settings.LIVEKIT_URL,
            job_memory_warn_mb=1024,
            agent_name="indusnet",
            entrypoint_fnc=entrypoint,
        )
    )
