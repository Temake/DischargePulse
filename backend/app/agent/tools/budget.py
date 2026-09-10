"""Call budget ledger.

The hackathon grants a small number of live calls. A runaway re-plan loop is the
realistic way to lose all of them at once, so every dial passes through a hard
ceiling that is persisted to disk and survives restarts.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings


class BudgetExhausted(RuntimeError):
    """Raised instead of dialing when the live call budget is spent."""

    def __init__(self, spent: int, ceiling: int) -> None:
        super().__init__(
            f"Live call budget exhausted: {spent}/{ceiling} calls used. "
            f"Raise CALL_BUDGET or switch TELEPHONY_MODE=replay."
        )
        self.spent = spent
        self.ceiling = ceiling


class CallBudget:
    """A persisted counter guarding live outbound dials.

    Only live calls are counted. Replayed cassettes are free and never touch the
    ledger.
    """

    def __init__(self, path: Path | None = None, ceiling: int | None = None) -> None:
        self._path = path or settings.budget_ledger_path
        self._ceiling = ceiling if ceiling is not None else settings.call_budget
        self._lock = threading.Lock()
        self._state = self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"spent": 0, "ceiling": self._ceiling, "calls": []}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    # -- api ----------------------------------------------------------------

    @property
    def spent(self) -> int:
        return int(self._state.get("spent", 0))

    @property
    def ceiling(self) -> int:
        return self._ceiling

    @property
    def remaining(self) -> int:
        return max(0, self._ceiling - self.spent)

    def check(self) -> None:
        """Raise if there is no headroom left. Call before dialing."""
        if self.remaining <= 0:
            raise BudgetExhausted(self.spent, self._ceiling)

    def reserve(self, facility_id: str, phone: str, note: str = "") -> int:
        """Consume one unit of budget and return the new spend count.

        Reserved *before* the dial rather than after, so a call that crashes
        mid-flight still counts - the credit was spent either way.
        """
        with self._lock:
            self.check()
            self._state["spent"] = self.spent + 1
            self._state["ceiling"] = self._ceiling
            self._state.setdefault("calls", []).append(
                {
                    "n": self._state["spent"],
                    "facility_id": facility_id,
                    "phone": phone,
                    "note": note,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
            self._flush()
            return self._state["spent"]

    def summary(self) -> str:
        return f"{self.spent}/{self._ceiling} live calls used, {self.remaining} remaining"


budget = CallBudget()
