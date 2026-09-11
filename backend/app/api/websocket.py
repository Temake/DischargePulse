"""Live event stream for one placement run.

Protocol - every frame is a JSON object with a `type`:

    {"type": "hello", "run_id", "case_id", "status", "telephony"}
        Sent once on connect.

    {"type": "event", "event": AgentEvent}
        One step of the cognitive loop. On connect, every event the client
        missed is replayed first, then live events follow.

    {"type": "run", "run": RunRecord}
        Full snapshot, sent whenever the run changes state - on reaching a
        proposal, on no match, on failure, and on the case manager's decision.

The server closes the socket (code 1000) once the run is terminal. A run that is
awaiting approval keeps its socket open so the decision arrives live.
"""

from __future__ import annotations

import anyio
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)

from app.services.run_manager import RunChannel, RunManager, RunNotFound

router = APIRouter()

# Application-range close code (4000-4999) mirroring HTTP 404.
WS_RUN_NOT_FOUND = 4404


@router.websocket("/ws/runs/{run_id}")
async def run_stream(websocket: WebSocket, run_id: str) -> None:
    manager: RunManager = websocket.app.state.run_manager

    try:
        record = manager.get(run_id)
        channel = manager.channel(run_id)
    except RunNotFound:
        raise WebSocketException(
            code=WS_RUN_NOT_FOUND, reason=f"Unknown run {run_id}"
        )

    await websocket.accept()
    queue, backlog = channel.subscribe()

    async def pump() -> None:
        await websocket.send_json(
            {
                "type": "hello",
                "run_id": record.run_id,
                "case_id": record.case_id,
                "status": record.run.status.value,
                "telephony": record.telephony,
            }
        )
        for message in backlog:
            await websocket.send_json(message)
        while True:
            message = await queue.get()
            if RunChannel.is_closed_marker(message):
                return
            await websocket.send_json(message)

    async def watch_for_disconnect() -> None:
        # The console never needs to send anything; this exists only to notice
        # the client leaving so the subscription is released promptly.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    delivered = False

    # A task group, not bare asyncio tasks: when the server cancels this
    # handler (client gone, shutdown), cancellation must reach both children.
    # Tasks created outside the handler's cancel scope get orphaned instead.
    try:
        async with anyio.create_task_group() as group:

            async def run_pump() -> None:
                nonlocal delivered
                try:
                    await pump()
                    delivered = True
                except (WebSocketDisconnect, RuntimeError):
                    pass  # client vanished mid-send
                group.cancel_scope.cancel()

            async def run_watch() -> None:
                await watch_for_disconnect()
                group.cancel_scope.cancel()

            group.start_soon(run_pump)
            group.start_soon(run_watch)
    finally:
        channel.unsubscribe(queue)

    if delivered:
        # The run reached a terminal state and everything has been delivered.
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
