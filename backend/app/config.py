"""Environment configuration for DischargePulse."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

load_dotenv(PROJECT_ROOT / ".env")


class TelephonyMode(str, Enum):
    """How the agent reaches the outside world."""

    LIVE = "live"
    REPLAY = "replay"
    AUTO = "auto"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    calle_api_key: str | None = None

    telephony_mode: TelephonyMode = TelephonyMode.REPLAY
    record_cassettes: bool = True

    # Hard ceiling checked before every dial. The hackathon grants 20 calls and
    # a runaway re-plan loop is the realistic way to lose them all at once.
    call_budget: int = 20
    max_concurrent_calls: int = 6

    demo_phone_primary: str | None = None
    demo_phone_secondary: str | None = None

    cassette_dir: Path = BACKEND_ROOT / "cassettes"
    artifact_dir: Path = BACKEND_ROOT / "artifacts"
    budget_ledger_path: Path = BACKEND_ROOT / ".call_budget.json"

    @property
    def can_call_live(self) -> bool:
        return bool(self.calle_api_key)

    def resolve_mode(self) -> TelephonyMode:
        """Collapse AUTO into a concrete mode."""
        if self.telephony_mode is not TelephonyMode.AUTO:
            return self.telephony_mode
        return TelephonyMode.LIVE if self.can_call_live else TelephonyMode.REPLAY


settings = Settings()
settings.cassette_dir.mkdir(parents=True, exist_ok=True)
settings.artifact_dir.mkdir(parents=True, exist_ok=True)
