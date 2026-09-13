"""Tests for the bounded LLM roles: transcript reviewer and case-manager brief.

Every test uses a fake backend - nothing reaches the Claude API. The reviewer's
guard rules are the point, so each has its own test: the model may only make the
agent more cautious, and only by quoting the facility's own words verbatim.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.agent.llm.brief import CaseManagerBriefer, provenance_note
from app.agent.llm.claude import FALLBACK_BETA, ClaudeBackend, LLMUnavailable
from app.agent.llm.reviewer import TranscriptReviewer, review_label
from app.agent.placement_agent import PlacementAgent
from app.agent.reasoning_engine import ReasoningEngine
from app.agent.tools.simulated_attendant import ScriptedAttendantActuator
from app.data.synthetic_data import get_facility
from app.models.schemas import (
    AgentPhase,
    AnswersSource,
    Disposition,
    RunStatus,
    TranscriptSpeaker,
    TranscriptTurn,
    VerificationState,
)
from tests.conftest import ScriptedActuator, answers, make_observation

CAVEAT = "Yes, we can take the wound VAC patient, but only once our certified nurse is back on Thursday."


class FakeBackend:
    model = "claude-opus-5"

    def __init__(self, flags=None, error=None, brief="Recommendation: test brief."):
        self.flags = flags or []
        self.error = error
        self.brief = brief
        self.prompts: list[str] = []
        self.schemas: list[dict] = []

    async def structured(self, *, system, prompt, schema, max_tokens=16000):
        self.prompts.append(prompt)
        self.schemas.append(schema)
        if self.error:
            raise LLMUnavailable(self.error)
        return {"flags": self.flags}, "claude-opus-5"

    async def text(self, *, system, prompt, max_tokens=16000):
        self.prompts.append(prompt)
        if self.error:
            raise LLMUnavailable(self.error)
        return self.brief, "claude-opus-5"


def flag(code="wound_vac", state="not_confirmed", quote="only once our certified nurse is back on Thursday", reason="Conditional on Thursday."):
    return {"code": code, "proposed_state": state, "quote": quote, "reason": reason}


def evaluated(patient, facility_id="SNF-004", result=None, turns=None, **obs):
    facility = get_facility(facility_id)
    observation = make_observation(facility_id, structured_result=result or answers(), **obs)
    observation = observation.model_copy(update={"transcript_turns": turns if turns is not None else [
        TranscriptTurn(offset_seconds=2, speaker=TranscriptSpeaker.BOT, text="Can you take a patient with a wound VAC today?"),
        TranscriptTurn(offset_seconds=6, speaker=TranscriptSpeaker.USER, text=CAVEAT),
    ]})
    return facility, ReasoningEngine().evaluate(patient, facility, observation)


def review(backend, patient, facility, evaluation):
    return asyncio.run(TranscriptReviewer(backend).review(patient, facility, evaluation))


def state_of(evaluation, code):
    return next(f.state for f in evaluation.findings if f.code.value == code)


# ---------------------------------------------------------------------------
# Guard rules
# ---------------------------------------------------------------------------


class TestReviewerGuards:
    def test_verbatim_caveat_downgrades_and_rescores(self, patient):
        facility, before = evaluated(patient)
        assert before.disposition is Disposition.MATCH_VERIFIED

        after = review(FakeBackend([flag()]), patient, facility, before)

        assert state_of(after, "wound_vac") is VerificationState.NOT_CONFIRMED
        assert after.disposition is Disposition.NEEDS_FOLLOW_UP
        assert after.match_score < before.match_score
        accepted = after.review.accepted_flags[0]
        assert accepted.quote_source == "transcript"
        assert accepted.from_state is VerificationState.CONFIRMED

    def test_downgraded_finding_carries_the_quote_and_reason(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend([flag()]), patient, facility, before)
        finding = next(f for f in after.findings if f.code.value == "wound_vac")

        assert finding.quote == "only once our certified nurse is back on Thursday"
        assert "transcript review" in finding.rationale.lower()

    def test_it_can_never_move_a_finding_towards_confirmed(self, patient):
        facility, before = evaluated(patient, result=answers(wound_vac="no"))
        after = review(FakeBackend([flag(state="not_confirmed")]), patient, facility, before)

        assert state_of(after, "wound_vac") is VerificationState.EXPLICITLY_UNAVAILABLE
        assert after.review.flags[0].accepted is False
        assert "more cautious" in after.review.flags[0].rejection_reason

    def test_restating_the_current_state_is_rejected(self, patient):
        facility, before = evaluated(patient, result=answers(wound_vac="unknown"))
        after = review(FakeBackend([flag(state="not_confirmed")]), patient, facility, before)

        assert after.review.flags[0].accepted is False

    def test_a_paraphrase_is_rejected(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend([flag(quote="the certified nurse returns on Thursday")]), patient, facility, before)

        assert state_of(after, "wound_vac") is VerificationState.CONFIRMED
        assert "verbatim" in after.review.flags[0].rejection_reason
        assert after.disposition is Disposition.MATCH_VERIFIED

    def test_the_hospital_callers_words_cannot_be_cited(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend([flag(quote="Can you take a patient with a wound VAC today")]), patient, facility, before)

        assert after.review.flags[0].accepted is False
        assert state_of(after, "wound_vac") is VerificationState.CONFIRMED

    def test_a_trivially_short_quote_proves_nothing(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend([flag(quote="Yes")]), patient, facility, before)

        assert after.review.flags[0].accepted is False

    def test_a_requirement_the_patient_does_not_have_is_rejected(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend([flag(code="bariatric_capacity")]), patient, facility, before)

        rejected = after.review.flags[0]
        assert rejected.accepted is False
        assert rejected.code is None
        assert "bariatric_capacity" in rejected.rejection_reason

    def test_quote_matching_tolerates_typographic_quotes_and_spacing(self, patient):
        facility, before = evaluated(patient, turns=[
            TranscriptTurn(offset_seconds=6, speaker=TranscriptSpeaker.USER,
                           text="We’ll   only take it once the nurse’s sign-off is done."),
        ])
        after = review(FakeBackend([flag(quote="we'll only take it once the nurse's sign-off is done")]), patient, facility, before)

        assert after.review.flags[0].accepted is True

    def test_backend_failure_leaves_the_rule_result_untouched(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend(error="Claude credentials missing or invalid"), patient, facility, before)

        assert after.review.error == "Claude credentials missing or invalid"
        assert after.findings == before.findings
        assert after.disposition is before.disposition

    def test_no_flags_means_no_change(self, patient):
        facility, before = evaluated(patient)
        after = review(FakeBackend([]), patient, facility, before)

        assert after.review is not None and after.review.flags == []
        assert after.findings == before.findings

    def test_an_unusable_call_is_not_reviewed(self, patient):
        backend = FakeBackend([flag()])
        facility = get_facility("SNF-004")
        unreached = ReasoningEngine().evaluate(
            patient, facility, make_observation("SNF-004", structured_result=None)
        )

        result = review(backend, patient, facility, unreached)

        assert result.review is None
        assert backend.prompts == []

    def test_schema_only_offers_cautious_states_and_real_requirements(self, patient):
        backend = FakeBackend([])
        facility, before = evaluated(patient)
        review(backend, patient, facility, before)
        item = backend.schemas[0]["properties"]["flags"]["items"]["properties"]

        assert item["proposed_state"]["enum"] == ["not_confirmed", "explicitly_unavailable"]
        assert set(item["code"]["enum"]) == {r.code.value for r in patient.hard_requirements()}


class TestSimulatedEvidence:
    """Simulated answers are judged against the simulated statements, never
    against a real transcript that did not produce them."""

    def simulated(self, patient):
        return evaluated(
            patient,
            result=answers(wound_vac_detail="We can take the VAC, but only if the family brings the pump."),
            turns=[TranscriptTurn(offset_seconds=79, speaker=TranscriptSpeaker.USER,
                                  text="I'm sorry. There is signal interference on our call.")],
        )

    def as_simulated(self, facility, evaluation):
        obs = evaluation.observation.model_copy(update={"answers_source": AnswersSource.SIMULATED})
        return evaluation.model_copy(update={"observation": obs})

    def test_the_real_transcript_is_not_offered_as_evidence(self, patient):
        backend = FakeBackend([])
        facility, evaluation = self.simulated(patient)
        review(backend, patient, facility, self.as_simulated(facility, evaluation))

        assert "signal interference" not in backend.prompts[0]
        assert "simulated" in backend.prompts[0].lower()

    def test_a_transcript_quote_cannot_downgrade_simulated_answers(self, patient):
        facility, evaluation = self.simulated(patient)
        after = review(
            FakeBackend([flag(quote="There is signal interference on our call")]),
            patient, facility, self.as_simulated(facility, evaluation),
        )

        assert after.review.flags[0].accepted is False

    def test_a_simulated_statement_can_be_cited_and_is_labelled(self, patient):
        facility, evaluation = self.simulated(patient)
        after = review(
            FakeBackend([flag(quote="only if the family brings the pump")]),
            patient, facility, self.as_simulated(facility, evaluation),
        )

        accepted = after.review.accepted_flags[0]
        assert accepted.quote_source == "simulated answers"
        assert review_label(after) == "review of the simulated answers"


# ---------------------------------------------------------------------------
# Inside the agent loop
# ---------------------------------------------------------------------------


class TestReviewInTheLoop:
    def caveat_script(self):
        snf004 = make_observation("SNF-004", structured_result=answers(coordinator="Marcus")).model_copy(
            update={"transcript_turns": [TranscriptTurn(offset_seconds=6, speaker=TranscriptSpeaker.USER, text=CAVEAT)]}
        )
        return ScriptedActuator({
            "SNF-001": answers(wound_vac="no", sister="Bayview Peninsula Campus"),
            "SNF-003": answers(bed="no"),
            "SNF-004": snf004,
        })

    def test_review_event_follows_the_rule_event(self, patient):
        run = asyncio.run(PlacementAgent(ScriptedActuator({"SNF-001": answers()}), reviewer=TranscriptReviewer(FakeBackend([]))).run(patient))
        reasons = [e.message for e in run.events if e.phase is AgentPhase.REASON and e.facility_id == "SNF-001"]

        assert len(reasons) == 2
        assert "transcript review found nothing the rules missed" in reasons[1]

    def test_a_caveat_stops_the_agent_proposing_that_facility(self, patient):
        """Without review SNF-004 is proposed. With it, the Thursday caveat means
        it is not a verified match for a discharge today."""
        without = asyncio.run(PlacementAgent(self.caveat_script()).run(patient))
        with_review = asyncio.run(
            PlacementAgent(self.caveat_script(), reviewer=TranscriptReviewer(FakeBackend([flag()]))).run(patient)
        )

        assert without.proposal.facility_id == "SNF-004"
        assert with_review.status is not RunStatus.AWAITING_APPROVAL or with_review.proposal.facility_id != "SNF-004"
        downgrade = next(e for e in with_review.events if "downgraded" in e.message)
        assert "wound_vac -> not_confirmed" in downgrade.message

    def test_no_reviewer_means_no_review_events(self, patient):
        run = asyncio.run(PlacementAgent(ScriptedActuator({"SNF-001": answers()})).run(patient))

        assert not any("review" in e.message for e in run.events)

    def test_review_failure_is_announced_and_the_run_carries_on(self, patient):
        run = asyncio.run(PlacementAgent(
            ScriptedActuator({"SNF-001": answers()}),
            reviewer=TranscriptReviewer(FakeBackend(error="Could not reach the Claude API")),
        ).run(patient))

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert any("unavailable (Could not reach the Claude API); rule-based result stands" in e.message for e in run.events)


# ---------------------------------------------------------------------------
# Case-manager brief
# ---------------------------------------------------------------------------


class TestBrief:
    def proposed(self, patient, actuator=None, **agent):
        return asyncio.run(PlacementAgent(actuator or ScriptedActuator({"SNF-001": answers()}), **agent).run(patient))

    def test_every_proposal_has_a_brief_even_without_a_model(self, patient):
        run = self.proposed(patient)

        assert run.proposal.brief_source == "template"
        assert run.proposal.brief_model is None
        assert "Recommendation:" in run.proposal.brief

    def test_the_model_brief_is_used_and_attributed(self, patient):
        run = self.proposed(patient, briefer=CaseManagerBriefer(FakeBackend(brief="Recommendation: from Claude.")))

        assert run.proposal.brief_source == "llm"
        assert run.proposal.brief_model == "claude-opus-5"
        assert "Recommendation: from Claude." in run.proposal.brief

    def test_model_failure_falls_back_to_the_template(self, patient):
        run = self.proposed(patient, briefer=CaseManagerBriefer(FakeBackend(error="Claude rate limit reached")))

        assert run.proposal.brief_source == "template"

    def test_provenance_is_written_by_code_not_the_model(self, patient):
        """Even a model brief that says nothing about provenance gets the line."""
        run = self.proposed(patient, briefer=CaseManagerBriefer(FakeBackend(brief="Recommendation: fine.")))

        assert run.proposal.brief.startswith("Provenance:")

    def test_simulated_answers_are_named_in_the_brief(self, patient):
        run = self.proposed(patient, actuator=ScriptedAttendantActuator())

        assert "SIMULATED" in run.proposal.brief
        assert "0 live call(s) placed" in provenance_note(run)


# ---------------------------------------------------------------------------
# Claude backend against a fake SDK client
# ---------------------------------------------------------------------------


class FakeSDK:
    def __init__(self, response):
        self.response = response
        self.kwargs = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def sdk_response(text='{"flags": []}', stop_reason="end_turn", model="claude-opus-5"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="bio") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
    )


class TestClaudeBackend:
    def test_structured_request_shape(self):
        sdk = FakeSDK(sdk_response())
        backend = ClaudeBackend("claude-opus-5", 30.0, client=sdk)

        data, model = asyncio.run(backend.structured(system="s", prompt="p", schema={"type": "object"}))

        assert data == {"flags": []}
        assert sdk.kwargs["model"] == "claude-opus-5"
        assert sdk.kwargs["betas"] == [FALLBACK_BETA]
        assert sdk.kwargs["fallbacks"] == "default"
        assert sdk.kwargs["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}}

    def test_served_model_is_reported_not_assumed(self):
        """A refusal fallback serves from another model; record which one."""
        backend = ClaudeBackend("claude-opus-5", 30.0, client=FakeSDK(sdk_response(model="claude-opus-4-8")))

        _, model = asyncio.run(backend.text(system="s", prompt="p"))

        assert model == "claude-opus-4-8"

    @pytest.mark.parametrize("response, reason", [
        (sdk_response(stop_reason="refusal"), "declined"),
        (sdk_response(stop_reason="max_tokens"), "cut off"),
        (sdk_response(text="not json"), "invalid JSON"),
    ])
    def test_unusable_responses_raise_llm_unavailable(self, response, reason):
        backend = ClaudeBackend("claude-opus-5", 30.0, client=FakeSDK(response))

        with pytest.raises(LLMUnavailable, match=reason):
            asyncio.run(backend.structured(system="s", prompt="p", schema={}))


class RaisingSDK:
    def __init__(self, exc):
        self.exc = exc
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        raise self.exc


class TestNoCredentials:
    """Regression: with no Claude credentials the SDK raises a plain TypeError,
    which escaped the handler and would have crashed the whole placement run."""

    def test_non_api_errors_become_llm_unavailable(self):
        backend = ClaudeBackend(
            "claude-opus-5", 30.0,
            client=RaisingSDK(TypeError("Could not resolve authentication method.")),
        )

        with pytest.raises(LLMUnavailable, match="set ANTHROPIC_API_KEY"):
            asyncio.run(backend.text(system="s", prompt="p"))

    def test_missing_credentials_are_not_retried_for_every_facility(self):
        sdk = RaisingSDK(TypeError("Could not resolve authentication method."))
        calls = []
        original = sdk.create

        async def counting(**kwargs):
            calls.append(1)
            return await original(**kwargs)

        sdk.beta.messages.create = counting
        backend = ClaudeBackend("claude-opus-5", 30.0, client=sdk)
        for _ in range(3):
            with pytest.raises(LLMUnavailable):
                asyncio.run(backend.text(system="s", prompt="p"))

        assert len(calls) == 1

    def test_a_run_survives_missing_credentials(self, patient):
        backend = ClaudeBackend(
            "claude-opus-5", 30.0,
            client=RaisingSDK(TypeError("Could not resolve authentication method.")),
        )
        run = asyncio.run(PlacementAgent(
            ScriptedActuator({"SNF-001": answers()}),
            reviewer=TranscriptReviewer(backend),
            briefer=CaseManagerBriefer(backend),
        ).run(patient))

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert run.proposal.brief_source == "template"
        assert run.evaluations[0].review.error
