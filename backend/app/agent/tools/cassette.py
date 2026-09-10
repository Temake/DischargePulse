"""Cassette recording and playback.

A cassette is a real CALL-E call, saved to disk. The fallback path replays
genuine recorded calls rather than hand-written dialogue, so development and
rehearsal cost no call credit while the transcripts stay authentic. Every
replayed observation is stamped `mode=REPLAY` and keeps the original call's
identifiers, so a replay can always be traced back to the live call it came from.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.schemas import CallMode, CallObservation


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def cassette_path(case_id: str, facility_id: str, directory: Path | None = None) -> Path:
    root = directory or settings.cassette_dir
    return root / f"{_slug(case_id)}__{_slug(facility_id)}.json"


def record(
    observation: CallObservation,
    case_id: str,
    directory: Path | None = None,
) -> Path:
    """Persist a live observation so it can be replayed for free later."""
    path = cassette_path(case_id, observation.facility_id, directory)
    path.parent.mkdir(parents=True, exist_ok=True)

    envelope = {
        "cassette_version": 1,
        "case_id": case_id,
        "facility_id": observation.facility_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": observation.mode.value,
        "observation": json.loads(observation.model_dump_json()),
    }
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    return path


def load(
    case_id: str,
    facility_id: str,
    directory: Path | None = None,
) -> CallObservation | None:
    """Load a recorded observation, re-stamped as a replay."""
    path = cassette_path(case_id, facility_id, directory)
    if not path.exists():
        return None

    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    observation = CallObservation.model_validate(envelope["observation"])
    # Provenance is rewritten on the way out. The call_id and provider_call_id
    # of the original live call are preserved so the replay stays auditable.
    observation.mode = CallMode.REPLAY
    return observation


def available(directory: Path | None = None) -> list[Path]:
    root = directory or settings.cassette_dir
    return sorted(root.glob("*.json"))
