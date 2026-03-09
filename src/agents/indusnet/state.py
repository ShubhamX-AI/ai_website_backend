import asyncio
import datetime as dt
from typing import Optional

# Maximum number of screen snapshots kept per session.
_UI_SNAPSHOT_MAX_HISTORY = 10


class AgentState:
    """
    Holds all mutable runtime state for the IndusNetAgent.

    Separating state from behavior keeps __init__ lean and makes
    state fields easy to find, document, and reset if needed.
    """

    def _init_state(self) -> None:
        """Initialise all state fields. Call this from IndusNetAgent.__init__."""

        # ── Vector DB ──────────────────────────────────────────────
        self.db_fetch_size: int = 10
        self.db_results: str = ""

        # ── User Context ───────────────────────────────────────────
        self.user_id: Optional[str] = None
        self.user_name: Optional[str] = None
        self.user_email: Optional[str] = None
        self.user_phone: Optional[str] = None

        # ── UI Context ─────────────────────────────────────────────
        self._active_elements: list[str] = []

        # Ordered list of every screen shown this session (oldest → newest).
        # Bounded to _UI_SNAPSHOT_MAX_HISTORY; oldest entry evicted on overflow.
        self._ui_snapshot_history: list[dict] = []

        # Integer index into _ui_snapshot_history.
        # Always reset to the newest entry after a push.
        # Can be moved backward/forward explicitly for targeted email.
        self._snapshot_pointer: int = -1  # -1 = sentinel "no history yet"

        # Email delivery bookkeeping
        self._last_email_recipient: Optional[str] = None
        self._last_email_sent_at: Optional[str] = None

        # ── Location State ─────────────────────────────────────────
        self._location_status: Optional[str] = None  # "success" | "denied" | "unsupported"
        self._user_lat: Optional[float] = None
        self._user_lng: Optional[float] = None
        self._user_address: Optional[str] = None
        self._location_accuracy: Optional[float] = None
        self._location_event: asyncio.Event = asyncio.Event()  # fired when frontend responds

    # ── Snapshot write ──────────────────────────────────────────────────────

    def _set_last_ui_snapshot(
        self,
        snapshot_type: str,
        title: str,
        summary: str,
        details: Optional[dict] = None,
        source_tool: str = "",
        links: Optional[list[str]] = None,
    ) -> None:
        """
        Push a canonical snapshot of what is now visible on the user's screen.

        Bounded to _UI_SNAPSHOT_MAX_HISTORY entries; oldest is evicted on overflow.
        Pointer is always reset to the newest entry after a push.
        """
        snapshot = {
            "type": snapshot_type,
            "title": title,
            "summary": summary,
            "details": details or {},
            "source_tool": source_tool,
            "links": links or [],
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        self._ui_snapshot_history.append(snapshot)
        if len(self._ui_snapshot_history) > _UI_SNAPSHOT_MAX_HISTORY:
            self._ui_snapshot_history.pop(0)
        self._snapshot_pointer = len(self._ui_snapshot_history) - 1

    # ── Snapshot read / navigation ──────────────────────────────────────────

    def _get_last_ui_snapshot(self) -> Optional[dict]:
        """
        Return the snapshot at the current pointer position.
        Defaults to the most recent screen after every push.
        Returns None when no screen has been shown yet this session.
        """
        if not self._ui_snapshot_history or self._snapshot_pointer < 0:
            return None
        return self._ui_snapshot_history[self._snapshot_pointer]

    def _get_snapshot_at_offset(self, offset: int) -> Optional[dict]:
        """
        Return the snapshot at (pointer + offset) without moving the pointer.

        offset=0  → current screen (same as _get_last_ui_snapshot)
        offset=-1 → one screen back from current pointer
        offset=-2 → two screens back, etc.

        Clamps safely to [0, len-1]; returns None if history is empty.
        """
        if not self._ui_snapshot_history or self._snapshot_pointer < 0:
            return None
        target = self._snapshot_pointer + offset
        target = max(0, min(target, len(self._ui_snapshot_history) - 1))
        return self._ui_snapshot_history[target]

    def _navigate_snapshot_back(self) -> Optional[dict]:
        """
        Move the pointer one step back and return that snapshot.
        Used when user says 'use the previous screen for email' without
        triggering a full UI re-render.
        Returns None (without moving) if already at the oldest entry.
        """
        if not self._ui_snapshot_history or self._snapshot_pointer <= 0:
            return None
        self._snapshot_pointer -= 1
        return self._ui_snapshot_history[self._snapshot_pointer]

    def _navigate_snapshot_forward(self) -> Optional[dict]:
        """
        Move the pointer one step forward (toward most recent) and return that snapshot.
        Returns None (without moving) if already at the newest entry.
        """
        if not self._ui_snapshot_history:
            return None
        max_idx = len(self._ui_snapshot_history) - 1
        if self._snapshot_pointer >= max_idx:
            return None
        self._snapshot_pointer += 1
        return self._ui_snapshot_history[self._snapshot_pointer]

    def _get_snapshot_history_titles(self) -> list[str]:
        """
        Return a human-readable list of all stored snapshots.
        Newest entry last; current pointer marked with *.
        """
        result = []
        for i, s in enumerate(self._ui_snapshot_history):
            marker = " *" if i == self._snapshot_pointer else ""
            result.append(f"[{i}] {s.get('title', '?')} ({s.get('type', '?')}){marker}")
        return result
