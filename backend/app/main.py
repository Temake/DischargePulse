"""FastAPI entrypoint for DischargePulse.

    cd backend
    python -m uvicorn app.main:app --reload --port 8000

Interactive API docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes, websocket
from app.config import settings
from app.services.run_manager import (
    RunConflict,
    RunManager,
    RunNotFound,
    RunRejected,
)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


def create_app(run_manager: RunManager | None = None) -> FastAPI:
    """Build the app. Tests pass their own RunManager to swap the actuator."""

    manager = run_manager or RunManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.run_manager = manager
        yield
        await manager.shutdown()

    app = FastAPI(
        title="DischargePulse",
        description=(
            "Autonomous post-acute placement agent using CALL-E as a telephony "
            "actuator. Audit-ready prototype using synthetic healthcare data."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    # Also set eagerly, so the manager is reachable even if a client skips the
    # lifespan (e.g. a TestClient used without a `with` block).
    app.state.run_manager = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RunNotFound)
    async def _not_found(_: Request, exc: RunNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Not found: {exc}"})

    @app.exception_handler(RunConflict)
    async def _conflict(_: Request, exc: RunConflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RunRejected)
    async def _rejected(_: Request, exc: RunRejected) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(routes.router)
    app.include_router(websocket.router)
    return app


app = create_app()
