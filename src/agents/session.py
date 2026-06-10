from collections import deque
import logging
import asyncio
import os
import random
from livekit import rtc
from livekit.agents import (
    WorkerOptions,
    AgentSession,
    JobContext,
    cli,
    BackgroundAudioPlayer,
    AudioConfig,
    room_io,
)
from livekit.plugins import sarvam, silero, openai
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from src.core.config import settings
from src.core.logger import setup_logging
from src.agents.indusnet.agent import IndusNetAgent
from src.agents.indusnet.helpers.filler import generate_filler
from src.agents.indusnet.helpers.silence import (
    AgentIdleShutdownController,
    SilenceWatchdogController,
)

setup_logging()
logger = logging.getLogger(__name__)


def prewarm(proc):
    """Load Silero VAD once per worker process and reuse across jobs."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    session = AgentSession(
        # Speech-to-text: Sarvam saaras:v3, transcribe mode keeps original spoken language
        stt=sarvam.STT(
            model="saaras:v3",
            mode="transcribe",
            api_key=settings.SARVAM_API_KEY,
        ),
        # LLM: OpenAI GPT-4.1 over Chat Completions
        llm=openai.LLM(
            model="gpt-4.1",
            api_key=settings.OPENAI_API_KEY,
            temperature=0.2,
        ),
        # Text-to-speech: Sarvam bulbul:v3
        tts=sarvam.TTS(
            model="bulbul:v3",
            speaker="simran",
            target_language_code="en-IN",
            api_key=settings.SARVAM_API_KEY,
            pace=1.0,
        ),
        # Silence detection + semantic end-of-utterance turn detection
        vad=ctx.proc.userdata["vad"],
        turn_detection=MultilingualModel(),
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

    # Recent completed turns — passed to filler LLM for emotional context
    _context_turns: deque = deque(maxlen=4)

    # Configure room options
    room_options = room_io.RoomOptions(
        text_input=True,
        audio_input=True,
        audio_output=True,
        close_on_disconnect=True,
        delete_room_on_close=True,
    )

    await session.start(agent=agent_instance, room=ctx.room, room_options=room_options)

    silence_watchdog = SilenceWatchdogController(session=session, logger=logger)
    agent_idle_shutdown = AgentIdleShutdownController(session=session, logger=logger)
    user_is_speaking = False

    # ── Filler pipeline ───────────────────────────────────────────────────────
    # Uses VAD state to schedule/cancel the filler loop. Each loop fires a
    # standalone LLM call (gpt-4o-mini) with the last 4 conversation turns so
    # the phrase matches the emotional tone of the conversation.

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        """Forward agent runtime state to idle timeout controller."""
        agent_idle_shutdown.on_agent_state_changed(ev.new_state)

    @session.on("conversation_item_added")
    def on_conversation_item_added(ev):
        """Store turn context and update silence tracking."""
        msg = ev.item
        if hasattr(msg, "role") and hasattr(msg, "text_content") and msg.text_content:
            if msg.role in ("user", "assistant"):
                _context_turns.append({"role": msg.role, "text": msg.text_content})

            if msg.role == "user":
                silence_watchdog.on_user_message()
                return

            if msg.role == "assistant":
                if user_is_speaking:
                    return
                silence_watchdog.on_assistant_message(msg.text_content)

    async def _filler_loop():
        """Fire fillers while the user speaks: first at 2-3s, then every 5-8s."""
        await asyncio.sleep(random.uniform(2.0, 3.0))
        while True:
            text = await generate_filler(list(_context_turns))
            if text:
                logger.debug(f"[filler] saying: {text!r}")
                await session.say(text, allow_interruptions=True)
            await asyncio.sleep(random.uniform(5.0, 8.0))

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        """Start/stop filler and silence timers based on VAD state."""
        nonlocal user_is_speaking
        is_speaking = ev.new_state == "speaking"
        user_is_speaking = is_speaking
        silence_watchdog.on_user_state_changed(is_speaking)

        if is_speaking:
            if agent_instance._filler_task and not agent_instance._filler_task.done():
                agent_instance._filler_task.cancel()
            agent_instance._filler_task = asyncio.create_task(_filler_loop())
            logger.debug("[filler] user started speaking — loop started")
        else:
            if agent_instance._filler_task and not agent_instance._filler_task.done():
                agent_instance._filler_task.cancel()
                logger.debug("[filler] user stopped speaking — loop cancelled")

    # ─────────────────────────────────────────────────────────────────────────

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

    agent_idle_shutdown.stop()
    silence_watchdog.stop()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            ws_url=settings.LIVEKIT_URL,
            job_memory_warn_mb=1024,
            agent_name="indusnet",
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
