"""Durable storage for placement-run snapshots.

The agent keeps a complete, typed ``RunRecord`` in memory while it is executing
so WebSocket updates remain immediate.  This repository mirrors each snapshot
to Postgres (Neon in deployment), giving the console an audit history that
survives a process restart without coupling the agent to a particular ORM.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class RunStore:
    """Small Postgres repository backed by one JSONB snapshot per run.

    ``database_url=None`` intentionally keeps local scripted development
    dependency-free.  A configured URL is fail-closed: losing the audit store
    must not silently turn a deployment back into an in-memory-only service.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url
        if database_url:
            self._ensure_schema()

    @property
    def enabled(self) -> bool:
        return self._database_url is not None

    def _connect(self):
        if not self._database_url:
            raise RuntimeError("Run store is not configured")
        try:
            import psycopg
        except ImportError as exc:  # clearer than a module traceback at deploy time
            raise RuntimeError(
                "DATABASE_URL is set but psycopg is not installed. "
                "Install backend requirements.txt."
            ) from exc
        return psycopg.connect(self._database_url, autocommit=True)

    def _ensure_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS placement_runs (
                    run_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    telephony TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS placement_runs_started_at_idx
                ON placement_runs (started_at DESC);
                """
            )

    def save(self, record: Any) -> None:
        """Insert or replace the current durable snapshot for one run."""
        if not self._database_url:
            return
        from psycopg.types.json import Jsonb

        payload = record.model_dump(mode="json")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO placement_runs
                    (run_id, case_id, status, telephony, started_at, finished_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    case_id = EXCLUDED.case_id,
                    status = EXCLUDED.status,
                    telephony = EXCLUDED.telephony,
                    started_at = EXCLUDED.started_at,
                    finished_at = EXCLUDED.finished_at,
                    payload = EXCLUDED.payload,
                    updated_at = NOW();
                """,
                (
                    record.run_id,
                    record.case_id,
                    record.run.status.value,
                    record.telephony,
                    record.started_at,
                    record.finished_at,
                    Jsonb(payload),
                ),
            )

    def load_all(self) -> list[Any]:
        """Return durable snapshots, newest first, as plain JSON values."""
        if not self._database_url:
            return []
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT payload FROM placement_runs ORDER BY started_at DESC")
            return [row[0] for row in cur.fetchall()]
