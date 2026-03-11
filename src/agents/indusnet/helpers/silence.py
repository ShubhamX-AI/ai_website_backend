import asyncio
import logging
from typing import Final

from livekit.agents import AgentSession

REPROMPT_INTERVAL_SEC: Final[float] = 6.0
MAX_REPROMPTS: Final[int] = 2
AGENT_IDLE_TIMEOUT_SEC: Final[float] = 30.0


class SilenceWatchdogController:
    """Tracks user silence and ends the call after repeated reprompts."""

    def __init__(
        self,
        session: AgentSession,
        logger: logging.Logger,
        reprompt_interval_sec: float = REPROMPT_INTERVAL_SEC,
        max_reprompts: int = MAX_REPROMPTS,
    ) -> None:
        self._session = session
        self._logger = logger
        self._reprompt_interval_sec = reprompt_interval_sec
        self._max_reprompts = max_reprompts

        self._silence_task: asyncio.Task | None = None
        self._reprompt_count = 0
        self._waiting_for_user_response = False
        self._user_is_speaking = False
        self._skip_next_assistant_message = False

    def stop(self) -> None:
        """Stops silence tracking and cancels the watchdog task."""
        self._clear_waiting_state()

    def on_user_message(self) -> None:
        """Clears pending silence checks when the user replies."""
        self._logger.debug("[silence] user message received")
        self._clear_waiting_state()

    def on_assistant_message(self, message_text: str) -> None:
        """Starts or stops silence tracking based on assistant text."""
        if not message_text:
            return

        if self._skip_next_assistant_message:
            self._skip_next_assistant_message = False
            return

        if self._assistant_expects_reply(message_text):
            self._logger.debug("[silence] assistant expects a reply")
            self._waiting_for_user_response = True
            self._reprompt_count = 0
            self._cancel_watchdog_task()
            self._start_watchdog_task()
            return

        self._clear_waiting_state()

    def on_user_state_changed(self, is_speaking: bool) -> None:
        """Pauses watchdog while user speaks and resumes when they stop."""
        self._user_is_speaking = is_speaking
        if is_speaking:
            self._cancel_watchdog_task()
            return
        self._start_watchdog_task()

    def _assistant_expects_reply(self, message_text: str) -> bool:
        normalized_text = " ".join(message_text.lower().split())
        if "?" in normalized_text:
            return True

        reply_phrases = (
            "let me know",
            "tell me",
            "please respond",
            "can you",
            "could you",
            "would you",
            "share with me",
        )
        return any(phrase in normalized_text for phrase in reply_phrases)

    def _clear_waiting_state(self) -> None:
        self._waiting_for_user_response = False
        self._reprompt_count = 0
        self._cancel_watchdog_task()

    def _cancel_watchdog_task(self) -> None:
        silence_task = self._silence_task
        if silence_task and not silence_task.done():
            silence_task.cancel()
        self._silence_task = None

    def _start_watchdog_task(self) -> None:
        if not self._waiting_for_user_response or self._user_is_speaking:
            return
        if self._silence_task and not self._silence_task.done():
            return
        self._silence_task = asyncio.create_task(self._watchdog_loop())

    async def _watchdog_loop(self) -> None:
        try:
            while self._waiting_for_user_response:
                if self._reprompt_count >= self._max_reprompts:
                    self._logger.info("[silence] ending session after repeated silence")
                    self._clear_waiting_state()
                    self._session.shutdown()
                    return

                await asyncio.sleep(self._reprompt_interval_sec)

                if not self._waiting_for_user_response or self._user_is_speaking:
                    return

                self._reprompt_count += 1
                self._logger.info(
                    "[silence] reprompt %s/%s",
                    self._reprompt_count,
                    self._max_reprompts,
                )
                self._skip_next_assistant_message = True
                await self._session.generate_reply(
                    instructions=(
                        "The user seems silent. Ask in one short, friendly sentence if they are still there.\n\n"
                        "and request a quick response."
                    )
                )
        except asyncio.CancelledError:
            self._logger.debug("[silence] watchdog cancelled")
            raise
        except Exception:
            self._logger.exception("[silence] watchdog failed")
        finally:
            if asyncio.current_task() is self._silence_task:
                self._silence_task = None


class AgentIdleShutdownController:
    """Shuts down the session when the agent stays idle for too long."""

    def __init__(
        self,
        session: AgentSession,
        logger: logging.Logger,
        idle_timeout_sec: float = AGENT_IDLE_TIMEOUT_SEC,
    ) -> None:
        self._session = session
        self._logger = logger
        self._idle_timeout_sec = idle_timeout_sec

        self._current_agent_state = "initializing"
        self._idle_timeout_task: asyncio.Task | None = None

    def stop(self) -> None:
        """Stops idle-state tracking and cancels timeout task."""
        self._cancel_idle_timeout_task()

    def on_agent_state_changed(self, new_state: str) -> None:
        """Starts/cancels idle timeout based on agent runtime state."""
        self._current_agent_state = new_state
        self._logger.debug("[agent-idle] state changed to: %s", new_state)

        if new_state == "idle":
            self._cancel_idle_timeout_task()
            self._idle_timeout_task = asyncio.create_task(self._idle_timeout_loop())
            return

        self._cancel_idle_timeout_task()

    def _cancel_idle_timeout_task(self) -> None:
        idle_timeout_task = self._idle_timeout_task
        if idle_timeout_task and not idle_timeout_task.done():
            idle_timeout_task.cancel()
        self._idle_timeout_task = None

    async def _idle_timeout_loop(self) -> None:
        try:
            await asyncio.sleep(self._idle_timeout_sec)
            if self._current_agent_state != "idle":
                return

            self._logger.info(
                "[agent-idle] state stayed idle for %.1fs, shutting down session",
                self._idle_timeout_sec,
            )
            self._session.shutdown()
        except asyncio.CancelledError:
            self._logger.debug("[agent-idle] idle timeout task cancelled")
            raise
        except Exception:
            self._logger.exception("[agent-idle] idle timeout loop failed")
        finally:
            if asyncio.current_task() is self._idle_timeout_task:
                self._idle_timeout_task = None
