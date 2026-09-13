"""Bounded LLM roles in the agent: review findings and write the brief.

Neither role can confirm a requirement or approve a placement - see reviewer.py.
"""

from __future__ import annotations

import logging

from app.agent.llm.brief import CaseManagerBriefer
from app.agent.llm.claude import ClaudeBackend, LLMBackend, LLMUnavailable
from app.agent.llm.reviewer import TranscriptReviewer
from app.config import settings

log = logging.getLogger(__name__)


def build_llm_components() -> tuple[TranscriptReviewer | None, CaseManagerBriefer]:
    """The reviewer (or None when disabled) and a briefer that always works.

    The briefer is returned even with the LLM off: it falls back to the template,
    so every proposal still carries a brief.
    """
    if not settings.llm_review_enabled:
        return None, CaseManagerBriefer(None)

    try:
        backend = ClaudeBackend(settings.llm_model, settings.llm_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - SDK missing or client unconstructable
        log.warning("LLM review disabled: %s", exc)
        return None, CaseManagerBriefer(None)

    return TranscriptReviewer(backend), CaseManagerBriefer(backend)


__all__ = [
    "CaseManagerBriefer",
    "ClaudeBackend",
    "LLMBackend",
    "LLMUnavailable",
    "TranscriptReviewer",
    "build_llm_components",
]
