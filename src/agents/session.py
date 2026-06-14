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


# Sarvam STT `prompt` (saaras:v3): per Sarvam docs, a "domain-specific prompt +
# hotword retention" hint — it biases the recognizer toward the conversation's
# domain and preserves the proper nouns/terms named here so they transcribe
# correctly. Natural language is valid (Sarvam's own example: "Transcribe Hindi
# conversation about technology."). This transcribes the CALLER's speech, so the
# terms below are what callers actually say. It is NOT a command parser — noise
# rejection is the VAD's job, not this.
STT_PROMPT = (
    "A caller is talking to the voice assistant of Indus Net Technologies "
    "(INT), an IT services and software company in Kolkata, India. The caller "
    "speaks English, Hindi, or Bengali and often mixes them (Hinglish, "
    "Banglish). Recognize and preserve these terms accurately."
)


async def entrypoint(ctx: JobContext):
    session = AgentSession(
        # Speech-to-text: Sarvam saaras:v3, codemix mode for mixed-language speech
        stt=sarvam.STT(
            model="saaras:v3",
            mode="codemix",
            api_key=settings.SARVAM_API_KEY,
            language="unknown",  # auto-detect language from speech
            prompt=STT_PROMPT,  # bias toward domain vocab + code-mixed speech
            # Noise rejection (saaras:v3 VAD) — reject faint/short background audio
            # so ambient room noise is not transcribed. Tune against real recordings.
            high_vad_sensitivity=False,
            positive_speech_threshold=0.85,
            negative_speech_threshold=0.35,
            min_speech_frames=8,
            # first_turn_min_speech_frames=4,
            num_initial_ignored_frames=4,
            # negative_frames_count=4,
            # negative_frames_window=3,
            # start_speech_volume_threshold=0.05,
        ),
        # LLM: OpenAI GPT-4.1 over Chat Completions
        llm=openai.LLM(
            model="gpt-4.1",
            api_key=settings.OPENAI_API_KEY,
            temperature=0.2,
            parallel_tool_calls=False,  # serialize tool calls; avoids racing UI data packets
            max_completion_tokens=300,  # short voice replies → lower latency, no rambling
            prompt_cache_key="indusnet",  # cache the large system prompt → latency + cost
        ),
        # Text-to-speech: Sarvam bulbul:v3 — fixed en-IN voice. The LLM writes
        # replies in the target language (Hinglish/Banglish); this voice speaks them.
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
        # ── Turn-taking + barge-in tuning (self-hosted; no Krisp BVC) ──────────
        # Barge-in must be FAST: when the user speaks over the agent it should stop
        # almost immediately. With min_interruption_words > 0 the agent keeps talking
        # until Sarvam STT transcribes a word — that STT lag was the 1–3s delay. So
        # interruption is voice-activity driven (min_interruption_words=0): the agent
        # PAUSES the instant VAD hears speech. Noise tolerance comes from the
        # pause→auto-resume model, not a word gate — resume_false_interruption=True
        # means a pause that yields no real speech resumes after false_interruption_timeout.
        allow_interruptions=True,            # keep barge-in (user can cut in)
        min_interruption_words=0,            # interrupt on voice activity, not on a transcribed word → instant stop
        min_interruption_duration=0.3,       # min VAD speech length before pausing; false pauses auto-resume
        resume_false_interruption=True,      # if a pause yields no speech (noise), resume the agent
        false_interruption_timeout=0.7,      # silence window after a pause to classify it as false → resume
        discard_audio_if_uninterruptible=True,  # drop audio captured while agent can't be interrupted
        # Endpointing: bound the semantic turn detector. Slightly larger min delay
        # so a brief mid-sentence pause (common in Hinglish/Banglish) doesn't end
        # the user's turn prematurely; cap the wait at 3s.
        min_endpointing_delay=0.3,
        max_endpointing_delay=0.6,
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

    # # Greet the participant
    # if participant.name:
    #     logger.info(f"Greeting user with name: {participant.name}")
    #     await session.generate_reply(
    #         instructions=f"Greet the user - **{participant.name}** professionally and friendly using their first name. Welcome them back to the website in English.",
    #         allow_interruptions=False,
    #     )
    # else:
    #     logger.info("Greeting user without name")
    #     await session.generate_reply(
    #         instructions="Greet the user in a professional and friendly manner in English.",
    #         allow_interruptions=False,
    #     )

    logger.info("Greeting user without name")
    await session.generate_reply(
        instructions="Start the conversation with a concise, professional, and friendly English greeting.",
        allow_interruptions=False,
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
