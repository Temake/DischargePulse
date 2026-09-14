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
    # Real calls; attendant answers simulated and labelled as such.
    SIMULATED = "simulated"
    # No calls; scenario answers labelled as scripted. Free, for rehearsals.
    SCRIPTED = "scripted"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    calle_api_key: str | None = None
    # A pooled Neon/Postgres URL. When present, all run snapshots and their
    # events are persisted; without it local development stays in-memory.
    database_url: str | None = None

    telephony_mode: TelephonyMode = TelephonyMode.REPLAY
    record_cassettes: bool = True

    # Hard ceiling checked before every dial. The hackathon grants 20 calls and
    # a runaway re-plan loop is the realistic way to lose them all at once.
    call_budget: int = 20
    max_concurrent_calls: int = 6

    demo_phone_primary: str | None = None
    demo_phone_secondary: str | None = None

    # LLM transcript review and case-manager brief (Claude). Credentials come
    # from ANTHROPIC_API_KEY or an `ant auth login` profile. With none available
    # the calls fail, are recorded, and the rule-based agent carries on.
    llm_review_enabled: bool = True
    # "anthropic" uses the Claude API (ANTHROPIC_API_KEY). "bedrock" uses Claude
    # on Amazon Bedrock with the standard AWS credential chain and AWS_REGION.
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-5"
    # Bedrock has no server-side refusal fallback, so a client-side middleware
    # retries a declined request on this model instead.
    llm_fallback_model: str = "claude-opus-4-8"
    llm_timeout_seconds: float = 90.0
    aws_region: str | None = None

    # Browser origins allowed to call the API. Defaults cover the Vite dev
    # server; set CORS_ORIGINS as a JSON list to override.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

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
