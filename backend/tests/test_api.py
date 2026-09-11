"""Tests for the REST API and the live WebSocket stream.

The app runs with a `RunManager` whose actuator factory hands back a
`ScriptedActuator`, so every test drives the real agent, planner and reasoning
engine end to end - through HTTP and WebSocket - without a phone or a network.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.agent.tools.budget import CallBudget
from app.config import TelephonyMode
from app.main import create_app
from app.services.run_manager import RunChannel, RunManager, StartRunRequest
from tests.conftest import ScriptedActuator, answers

DEMO_SCRIPT = {
    # SNF-001 contradicts its directory on wound VAC and names its sister
    # campus, which turns out to be the match - the story the video tells.
    "SNF-001": answers(
        wound_vac="no",
        wound_vac_detail="The night nurse isn't signed off on the VAC.",
        sister="Bayview Peninsula Campus",
    ),
    "SNF-003": answers(bed="no"),
    "SNF-004": answers(coordinator="Marcus", fax="555-0198"),
}

NO_MATCH_SCRIPT = {
    fid: answers(bed="no", sister="none")
    for fid in ["SNF-001", "SNF-003", "SNF-004", "SNF-005", "SNF-006"]
}


class LabelledActuator(ScriptedActuator):
    """A scripted actuator that reports whichever telephony label it is given,
    so the live-call guard rails can be exercised without dialing."""

    def __init__(self, script, label):
        super().__init__(script)
        self.mode_label = label


class StalledActuator(ScriptedActuator):
    """Never finishes a call - keeps a run in flight for concurrency tests."""

    async def call_facility(self, facility, patient, objective=None, result_schema=None):
        await asyncio.Event().wait()


def scripted_factory(script):
    def factory(request: StartRunRequest):
        if request.live_facility_ids:
            return LabelledActuator(script, "hybrid")
        if request.mode is TelephonyMode.LIVE:
            return LabelledActuator(script, "live")
        return ScriptedActuator(script)

    return factory


@pytest.fixture
def ledger(tmp_path):
    return CallBudget(path=tmp_path / "ledger.json", ceiling=20)


@pytest.fixture
def make_client(ledger):
    def build(script=DEMO_SCRIPT, factory=None):
        manager = RunManager(
            actuator_factory=factory or scripted_factory(script),
            call_budget=ledger,
        )
        return TestClient(create_app(run_manager=manager))

    return build


@pytest.fixture
def client(make_client):
    with make_client() as c:
        yield c


def wait_for_status(client, run_id, *statuses, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["run"]["status"] in statuses:
            return body
        time.sleep(0.02)
    raise AssertionError(f"Run {run_id} never reached {statuses}")


def start(client, **body):
    body.setdefault("case_id", "10482")
    response = client.post("/api/runs", json=body)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def receive_until(ws, predicate, limit=200):
    """Collect frames until one satisfies `predicate` (inclusive)."""
    frames = []
    for _ in range(limit):
        frame = ws.receive_json()
        frames.append(frame)
        if predicate(frame):
            return frames
    raise AssertionError("predicate never satisfied")


def drain(ws, limit=200):
    """Collect frames until the server closes the socket."""
    frames = []
    try:
        for _ in range(limit):
            frames.append(ws.receive_json())
    except WebSocketDisconnect:
        return frames
    raise AssertionError("server never closed the socket")


def is_run_frame(status):
    return lambda f: f["type"] == "run" and f["run"]["run"]["status"] == status


# ---------------------------------------------------------------------------
# System and reference data
# ---------------------------------------------------------------------------


class TestSystemEndpoints:
    def test_health_reports_budget_and_telephony(self, client):
        body = client.get("/api/health").json()

        assert body["status"] == "ok"
        assert body["budget"] == {"spent": 0, "ceiling": 20, "remaining": 20}
        assert body["synthetic_data_only"] is True
        assert "telephony_mode" in body

    def test_budget_reflects_the_ledger(self, client, ledger):
        ledger.reserve("SNF-001", "+15555550100")

        assert client.get("/api/budget").json()["remaining"] == 19

    def test_patients_are_listed(self, client):
        ids = {p["case_id"] for p in client.get("/api/patients").json()}

        assert ids == {"10482", "10483"}

    def test_patient_detail_carries_hard_and_soft_requirements(self, client):
        body = client.get("/api/patients/10482").json()
        kinds = {r["kind"] for r in body["requirements"]}

        assert kinds == {"hard", "soft"}
        assert body["synthetic"] is True

    def test_unknown_patient_is_404(self, client):
        assert client.get("/api/patients/99999").status_code == 404

    def test_facilities_are_nearest_first_with_dialable_flag(self, client):
        rows = client.get("/api/facilities").json()
        distances = [r["facility"]["distance_miles"] for r in rows]

        assert distances == sorted(distances)
        assert all(isinstance(r["dialable"], bool) for r in rows)

    def test_cors_allows_the_vite_dev_server(self, client):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# ---------------------------------------------------------------------------
# Run lifecycle over HTTP
# ---------------------------------------------------------------------------


class TestRunLifecycle:
    def test_start_returns_immediately_with_a_run_id(self, client):
        response = client.post("/api/runs", json={"case_id": "10482"})

        assert response.status_code == 202
        body = response.json()
        assert body["run_id"].startswith("run_")
        assert body["telephony"] == "scripted"

    def test_unknown_case_is_404(self, client):
        response = client.post("/api/runs", json={"case_id": "99999"})

        assert response.status_code == 404

    def test_run_reaches_the_human_gate_with_a_proposal(self, client):
        run_id = start(client)
        body = wait_for_status(client, run_id, "awaiting_approval")

        proposal = body["run"]["proposal"]
        assert proposal["facility_id"] == "SNF-004"
        assert proposal["status"] == "pending"
        assert body["finished_at"] is None  # still waiting on a human

    def test_snapshot_carries_the_contradiction(self, client):
        run_id = start(client)
        body = wait_for_status(client, run_id, "awaiting_approval")

        snf001 = next(
            e for e in body["run"]["evaluations"] if e["facility_id"] == "SNF-001"
        )
        assert snf001["contradictions"][0]["code"] == "wound_vac"
        assert snf001["disposition"] == "disqualified"

    def test_run_list_summarises_runs(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        rows = client.get("/api/runs").json()
        assert rows[0]["run_id"] == run_id
        assert rows[0]["proposed_facility"] == "Bayview Post-Acute - Peninsula Campus"

    def test_unknown_run_is_404(self, client):
        assert client.get("/api/runs/run_nope").status_code == 404

    def test_no_match_run_finishes_without_a_proposal(self, make_client):
        with make_client(NO_MATCH_SCRIPT) as client:
            run_id = start(client)
            body = wait_for_status(client, run_id, "no_match_found")

        assert body["run"]["proposal"] is None
        assert body["finished_at"] is not None

    def test_a_crashing_run_is_marked_failed(self, client, monkeypatch):
        async def boom(self, patient, run=None):
            raise RuntimeError("planner exploded")

        monkeypatch.setattr("app.services.run_manager.PlacementAgent.run", boom)
        run_id = start(client)
        body = wait_for_status(client, run_id, "failed")

        assert "planner exploded" in body["run"]["error"]


# ---------------------------------------------------------------------------
# Human-in-the-loop gate
# ---------------------------------------------------------------------------


class TestApprovalGate:
    def test_approval_records_who_decided(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        response = client.post(
            f"/api/runs/{run_id}/approve",
            json={"decided_by": "CM Rivera", "note": "Family agrees."},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["run"]["status"] == "approved"
        assert body["run"]["proposal"]["status"] == "approved"
        assert body["run"]["proposal"]["decided_by"] == "CM Rivera"
        assert body["run"]["proposal"]["decided_at"] is not None
        assert body["finished_at"] is not None

    def test_decline_is_recorded(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        body = client.post(
            f"/api/runs/{run_id}/decline", json={"decided_by": "CM Rivera"}
        ).json()

        assert body["run"]["status"] == "declined"
        assert body["run"]["proposal"]["status"] == "declined"

    def test_a_decision_cannot_be_made_twice(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")
        client.post(f"/api/runs/{run_id}/approve", json={"decided_by": "CM Rivera"})

        second = client.post(
            f"/api/runs/{run_id}/decline", json={"decided_by": "Someone Else"}
        )

        assert second.status_code == 409

    def test_nothing_to_approve_without_a_proposal(self, make_client):
        with make_client(NO_MATCH_SCRIPT) as client:
            run_id = start(client)
            wait_for_status(client, run_id, "no_match_found")

            response = client.post(
                f"/api/runs/{run_id}/approve", json={"decided_by": "CM Rivera"}
            )

        assert response.status_code == 409

    def test_approval_requires_a_named_decider(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        response = client.post(f"/api/runs/{run_id}/approve", json={"decided_by": ""})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Live-call guard rails
# ---------------------------------------------------------------------------


class TestLiveGuards:
    def test_all_live_run_must_set_a_call_ceiling(self, client):
        response = client.post("/api/runs", json={"case_id": "10482", "mode": "live"})

        assert response.status_code == 422
        assert "max_calls" in response.json()["detail"]

    def test_live_run_cannot_exceed_remaining_budget(self, client, ledger):
        for _ in range(18):
            ledger.reserve("SNF-001", "+15555550100")

        response = client.post(
            "/api/runs", json={"case_id": "10482", "mode": "live", "max_calls": 3}
        )

        assert response.status_code == 422
        assert "2 remain" in response.json()["detail"]

    def test_hybrid_refuses_a_facility_with_no_receiver(self, client):
        # SNF-003 is a directory entry with a placeholder number.
        response = client.post(
            "/api/runs",
            json={"case_id": "10482", "live_facility_ids": ["SNF-003"]},
        )

        assert response.status_code == 422
        assert "no demo receiver" in response.json()["detail"]

    def test_hybrid_refuses_an_unknown_facility(self, client):
        response = client.post(
            "/api/runs",
            json={"case_id": "10482", "live_facility_ids": ["SNF-999"]},
        )

        assert response.status_code == 422

    def test_live_request_is_refused_rather_than_silently_replayed(self, make_client):
        """If live telephony is unavailable the console must be told, not
        quietly handed recordings while it believes calls are going out."""
        with make_client(factory=lambda req: ScriptedActuator(DEMO_SCRIPT)) as client:
            response = client.post(
                "/api/runs",
                json={"case_id": "10482", "mode": "live", "max_calls": 2},
            )

        assert response.status_code == 422
        assert "unavailable" in response.json()["detail"]

    def test_only_one_live_run_at_a_time(self, make_client):
        def stalled_live(request):
            actuator = StalledActuator({})
            actuator.mode_label = "live"
            return actuator

        with make_client(factory=stalled_live) as client:
            first = client.post(
                "/api/runs", json={"case_id": "10482", "mode": "live", "max_calls": 2}
            )
            second = client.post(
                "/api/runs", json={"case_id": "10482", "mode": "live", "max_calls": 2}
            )

        assert first.status_code == 202
        assert second.status_code == 409

    def test_replay_runs_are_not_limited_to_one_at_a_time(self, client):
        first = client.post("/api/runs", json={"case_id": "10482"})
        second = client.post("/api/runs", json={"case_id": "10482"})

        assert first.status_code == second.status_code == 202


# ---------------------------------------------------------------------------
# WebSocket stream
# ---------------------------------------------------------------------------


class TestWebSocket:
    def test_late_subscriber_receives_the_full_history(self, client):
        """A console that connects after the run started - or reconnects after a
        refresh - must see every step it missed, not a half-empty loop."""
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            frames = receive_until(ws, is_run_frame("awaiting_approval"))

        assert frames[0]["type"] == "hello"
        assert frames[0]["telephony"] == "scripted"

        phases = [f["event"]["phase"] for f in frames if f["type"] == "event"]
        for phase in ["plan", "act", "observe", "reason", "replan", "awaiting_approval"]:
            assert phase in phases

    def test_stream_carries_the_contradiction(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            frames = receive_until(ws, is_run_frame("awaiting_approval"))

        contradictions = [
            c
            for f in frames
            if f["type"] == "event"
            for c in f["event"]["payload"].get("contradictions", [])
        ]
        assert contradictions[0]["code"] == "wound_vac"

    def test_approval_arrives_live_and_then_the_socket_closes(self, client):
        run_id = start(client)
        wait_for_status(client, run_id, "awaiting_approval")

        with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
            receive_until(ws, is_run_frame("awaiting_approval"))

            client.post(
                f"/api/runs/{run_id}/approve", json={"decided_by": "CM Rivera"}
            )
            tail = drain(ws)

        decision = [f for f in tail if f["type"] == "event"]
        assert "approved by CM Rivera" in decision[0]["event"]["message"]
        assert tail[-1]["type"] == "run"
        assert tail[-1]["run"]["run"]["status"] == "approved"

    def test_terminal_run_closes_the_socket(self, make_client):
        with make_client(NO_MATCH_SCRIPT) as client:
            run_id = start(client)
            wait_for_status(client, run_id, "no_match_found")

            with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
                frames = drain(ws)

        complete = [
            f for f in frames if f["type"] == "event" and f["event"]["phase"] == "complete"
        ]
        assert complete, "the no-match COMPLETE event must reach the stream"
        assert frames[-1]["run"]["run"]["status"] == "no_match_found"

    def test_unknown_run_is_refused(self, client):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/runs/run_nope") as ws:
                ws.receive_json()

        assert exc.value.code == 4404


# ---------------------------------------------------------------------------
# Channel semantics
# ---------------------------------------------------------------------------


class TestRunChannel:
    def test_messages_before_subscribing_arrive_as_backlog(self):
        channel = RunChannel()
        channel.publish({"n": 1})
        channel.publish({"n": 2})

        _, backlog = channel.subscribe()

        assert backlog == [{"n": 1}, {"n": 2}]

    def test_messages_after_subscribing_arrive_on_the_queue(self):
        channel = RunChannel()
        queue, backlog = channel.subscribe()
        channel.publish({"n": 1})

        assert backlog == []
        assert queue.get_nowait() == {"n": 1}

    def test_close_signals_every_subscriber(self):
        channel = RunChannel()
        queue, _ = channel.subscribe()
        channel.close()

        assert RunChannel.is_closed_marker(queue.get_nowait())

    def test_subscribing_to_a_closed_channel_gets_history_then_close(self):
        channel = RunChannel()
        channel.publish({"n": 1})
        channel.close()

        queue, backlog = channel.subscribe()

        assert backlog == [{"n": 1}]
        assert RunChannel.is_closed_marker(queue.get_nowait())

    def test_publishing_after_close_is_ignored(self):
        channel = RunChannel()
        channel.close()
        channel.publish({"n": 1})

        _, backlog = channel.subscribe()
        assert backlog == []

    def test_unsubscribed_queues_stop_receiving(self):
        channel = RunChannel()
        queue, _ = channel.subscribe()
        channel.unsubscribe(queue)
        channel.publish({"n": 1})

        assert queue.empty()
