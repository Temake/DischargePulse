"""Core domain schemas for DischargePulse.

Everything the agent reasons about is defined here. The telephony layer is kept
deliberately separate from these types: `CallObservation` is the only surface
where the outside world enters the system, and it carries provenance so a live
call and a replayed cassette are always distinguishable downstream.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


class ConstraintKind(str, Enum):
    """Hard constraints disqualify. Soft constraints only rank."""

    HARD = "hard"
    SOFT = "soft"


class ConstraintCode(str, Enum):
    """The operational requirements the agent verifies by phone.

    These are placement logistics, not clinical judgments - the agent asks
    whether a facility *can accept* a patient, never whether it *should*.
    """

    PAYER_NETWORK = "payer_network"
    STAFFED_BED = "staffed_bed"
    WOUND_VAC = "wound_vac"
    IV_INFUSION = "iv_infusion"
    CONTACT_ISOLATION = "contact_isolation"
    BARIATRIC_CAPACITY = "bariatric_capacity"

    # Soft
    DISTANCE = "distance"
    CMS_RATING = "cms_rating"
    PREFERRED_PARTNER = "preferred_partner"


HARD_CONSTRAINTS: frozenset[ConstraintCode] = frozenset(
    {
        ConstraintCode.PAYER_NETWORK,
        ConstraintCode.STAFFED_BED,
        ConstraintCode.WOUND_VAC,
        ConstraintCode.IV_INFUSION,
        ConstraintCode.CONTACT_ISOLATION,
        ConstraintCode.BARIATRIC_CAPACITY,
    }
)


class VerificationState(str, Enum):
    """What the phone call established about one requirement.

    NOT_CONFIRMED and EXPLICITLY_UNAVAILABLE are deliberately distinct: the
    first means nobody would commit to an answer, the second means the facility
    said no. They disqualify for different reasons and read differently to a
    case manager.
    """

    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"
    EXPLICITLY_UNAVAILABLE = "explicitly_unavailable"
    UNKNOWN = "unknown"


class Requirement(BaseModel):
    """One care-team requirement attached to a patient case."""

    code: ConstraintCode
    kind: ConstraintKind
    label: str
    detail: str = ""
    # Free text the voice agent should actually say, e.g. drug and cadence.
    ask_as: str = ""

    @property
    def is_hard(self) -> bool:
        return self.kind is ConstraintKind.HARD


# ---------------------------------------------------------------------------
# Patient and facilities  (synthetic only - see data/synthetic_data.py)
# ---------------------------------------------------------------------------


class PatientCase(BaseModel):
    """A de-identified synthetic discharge case."""

    case_id: str
    display_name: str
    age: int
    sex: str
    payer: str
    payer_plan: str
    weight_lbs: int
    hospital_day: int
    discharge_summary: str
    family_zip: str
    search_radius_miles: int = 15
    max_radius_miles: int = 30
    requirements: list[Requirement] = Field(default_factory=list)
    synthetic: bool = True

    def hard_requirements(self) -> list[Requirement]:
        return [r for r in self.requirements if r.is_hard]

    def soft_requirements(self) -> list[Requirement]:
        return [r for r in self.requirements if not r.is_hard]


class DirectoryClaim(BaseModel):
    """What the static healthcare directory *claims* a facility offers.

    This is the baseline that live call intelligence is diffed against - the
    contradiction engine exists because these records go stale.
    """

    code: ConstraintCode
    claimed_available: bool
    source: str = "Regional Post-Acute Directory"
    last_updated: str = ""


class Facility(BaseModel):
    facility_id: str
    name: str
    facility_type: str = "Skilled Nursing Facility"
    phone: str
    admissions_extension: str | None = None
    address: str
    zip_code: str
    distance_miles: float
    cms_star_rating: float
    preferred_partner: bool = False
    accepted_payers: list[str] = Field(default_factory=list)
    directory_claims: list[DirectoryClaim] = Field(default_factory=list)
    # Facilities under shared ownership - the agent asks about these on-call
    # and queues them when the primary is full.
    sister_facility_ids: list[str] = Field(default_factory=list)
    # Scenario for CALL-E's official test line, whose AI agent answers as
    # itself unless asked to role-play. Used only when this facility's phone
    # is that test line - never sent to a real facility.
    roleplay_brief: str | None = None
    synthetic: bool = True

    def claim_for(self, code: ConstraintCode) -> DirectoryClaim | None:
        return next((c for c in self.directory_claims if c.code is code), None)


# ---------------------------------------------------------------------------
# Telephony observations
# ---------------------------------------------------------------------------


class CallMode(str, Enum):
    """Provenance of an observation. Rendered in the UI on every call card."""

    LIVE = "live"
    REPLAY = "replay"


class TranscriptSpeaker(str, Enum):
    BOT = "bot"
    USER = "user"
    UNKNOWN = "unknown"


class TranscriptTurn(BaseModel):
    offset_seconds: int | None = None
    speaker: TranscriptSpeaker = TranscriptSpeaker.UNKNOWN
    text: str


class CallOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    NO_ANSWER = "no_answer"


class CallObservation(BaseModel):
    """The result of one facility call, whatever produced it.

    Both the live CALL-E actuator and the cassette replayer return this exact
    type, so nothing downstream - planner, reasoning engine, scoring, UI - can
    tell them apart except by reading `mode`. That is the point: there is no
    demo-only code path.
    """

    facility_id: str
    phone: str

    # --- provenance ---------------------------------------------------------
    mode: CallMode
    # True when the call asked CALL-E's test line to role-play an admissions
    # coordinator from a scenario brief. Records the request, not the outcome:
    # the transcript shows whether the answering agent actually played along.
    roleplay_requested: bool = False
    call_id: str | None = None
    provider_call_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None

    # --- CALL-E terminal payload -------------------------------------------
    outcome: CallOutcome = CallOutcome.COMPLETED
    structured_result: dict[str, Any] | None = None
    summary: str | None = None
    task_completed: bool | None = None
    confidence_score: float | None = None
    confidence_label: str | None = None
    evidence: list[str] = Field(default_factory=list)
    transcript_turns: list[TranscriptTurn] = Field(default_factory=list)

    failure_code: str | None = None
    failure_message: str | None = None

    recorded_at: datetime = Field(default_factory=_now)

    @property
    def is_usable(self) -> bool:
        """Did this call produce evidence worth reasoning over?"""
        return (
            self.outcome is CallOutcome.COMPLETED
            and self.structured_result is not None
        )


# ---------------------------------------------------------------------------
# Reasoning output
# ---------------------------------------------------------------------------


class ConstraintFinding(BaseModel):
    """How one requirement fared at one facility."""

    code: ConstraintCode
    kind: ConstraintKind
    label: str
    state: VerificationState
    quote: str | None = None
    rationale: str = ""


class Contradiction(BaseModel):
    """Live phone intelligence disagreeing with the static directory."""

    code: ConstraintCode
    label: str
    directory_says: str
    call_says: str
    quote: str | None = None
    resolution: str = "Live call intelligence overrides directory record."


class Disposition(str, Enum):
    MATCH_VERIFIED = "match_verified"
    DISQUALIFIED = "disqualified"
    NEEDS_FOLLOW_UP = "needs_follow_up"
    UNREACHED = "unreached"


class FacilityEvaluation(BaseModel):
    facility_id: str
    facility_name: str
    disposition: Disposition
    match_score: float = 0.0
    findings: list[ConstraintFinding] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    disqualifying_codes: list[ConstraintCode] = Field(default_factory=list)
    # Sister facilities *named on the call* - live evidence from admissions.
    sister_facility_leads: list[str] = Field(default_factory=list)
    # Sister facilities known only from directory ownership data. A weaker
    # signal, kept separate so it can never be presented as call evidence.
    ownership_leads: list[str] = Field(default_factory=list)
    coordinator_name: str | None = None
    callback_number: str | None = None
    fax_number: str | None = None
    observation: CallObservation | None = None

    @property
    def is_placeable(self) -> bool:
        return self.disposition is Disposition.MATCH_VERIFIED


# ---------------------------------------------------------------------------
# Agent lifecycle events (streamed to the console over WebSocket)
# ---------------------------------------------------------------------------


class AgentPhase(str, Enum):
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    REASON = "reason"
    REPLAN = "replan"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETE = "complete"


class ReplanTrigger(str, Enum):
    NO_BEDS_IN_RADIUS = "no_beds_in_radius"
    SISTER_FACILITY_LEAD = "sister_facility_lead"
    PAYER_MISMATCH = "payer_mismatch"
    CONTRADICTION_DISQUALIFIED = "contradiction_disqualified"
    EARLY_STOP_MATCH_FOUND = "early_stop_match_found"
    BUDGET_EXHAUSTED = "budget_exhausted"


class AgentEvent(BaseModel):
    """One entry in the cognitive-loop visualiser."""

    cycle: int
    phase: AgentPhase
    message: str
    facility_id: str | None = None
    trigger: ReplanTrigger | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Human-in-the-loop gate
# ---------------------------------------------------------------------------


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


class PlacementPlan(BaseModel):
    """The call strategy for one cycle of the loop."""

    cycle: int
    radius_miles: float
    queue: list[str] = Field(default_factory=list)
    rationale: str = ""
    # facility_id -> why it was filtered out before any call was placed
    excluded: dict[str, str] = Field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.queue


class RunStatus(str, Enum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    NO_MATCH_FOUND = "no_match_found"
    APPROVED = "approved"
    DECLINED = "declined"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Nothing further can happen to a run in a terminal state."""
        return self not in {RunStatus.RUNNING, RunStatus.AWAITING_APPROVAL}


class PlacementProposal(BaseModel):
    """What the agent hands a case manager.

    Nothing here is executed until a human approves it - the agent may search,
    call, reason and draft, but never dispatches a referral or transport on its
    own.
    """

    case_id: str
    facility_id: str
    facility_name: str
    match_score: float
    evaluation: FacilityEvaluation
    packet_path: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    proposed_at: datetime = Field(default_factory=_now)
    # Who made the human-in-the-loop decision, and when. Recorded for audit.
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


class PlacementRun(BaseModel):
    """One end-to-end execution of the placement loop."""

    case_id: str
    status: RunStatus = RunStatus.RUNNING
    cycles_used: int = 0
    calls_placed: int = 0
    plans: list[PlacementPlan] = Field(default_factory=list)
    evaluations: list[FacilityEvaluation] = Field(default_factory=list)
    events: list[AgentEvent] = Field(default_factory=list)
    proposal: PlacementProposal | None = None
    error: str | None = None

    def evaluation_for(self, facility_id: str) -> FacilityEvaluation | None:
        return next(
            (e for e in self.evaluations if e.facility_id == facility_id), None
        )

    @property
    def contradictions(self) -> list[Contradiction]:
        return [c for e in self.evaluations for c in e.contradictions]
