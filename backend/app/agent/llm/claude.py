"""Claude access for the transcript reviewer and the case-manager brief.

This is the only module that imports the Anthropic SDK. Everything above it
depends on the `LLMBackend` protocol, so tests substitute a fake and never reach
the network.

Every failure - missing credentials, network, rate limit, a refusal, truncated or
invalid output - surfaces as `LLMUnavailable`. Callers treat that as "no review"
and keep the rule-based result; the agent never stalls on the model.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

log = logging.getLogger(__name__)

# Server-side refusal fallback: if Claude declines a request, the API re-runs it
# on Anthropic's recommended fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    """The model could not produce a usable answer. Carries a short reason."""


class LLMBackend(Protocol):
    model: str

    async def structured(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_tokens: int = 16000
    ) -> tuple[dict[str, Any], str]:
        """Return (parsed JSON matching `schema`, model that served it)."""
        ...

    async def text(
        self, *, system: str, prompt: str, max_tokens: int = 16000
    ) -> tuple[str, str]:
        """Return (text, model that served it)."""
        ...


class ClaudeBackend:
    """`LLMBackend` over the Anthropic Messages API."""

    def __init__(self, model: str, timeout_seconds: float, client: Any = None) -> None:
        import anthropic

        self._anthropic = anthropic
        self.model = model
        self._client = client or anthropic.AsyncAnthropic(
            timeout=timeout_seconds, max_retries=2
        )
        # Set once credentials are known to be missing or rejected, so a run
        # does not retry - and log - the same failure for every facility.
        self._credential_error: str | None = None

    async def _create(self, **kwargs: Any) -> Any:
        if self._credential_error:
            raise LLMUnavailable(self._credential_error)
        a = self._anthropic
        try:
            response = await self._client.beta.messages.create(
                model=self.model,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                **kwargs,
            )
        except a.AuthenticationError as exc:
            self._credential_error = "Claude credentials invalid - check ANTHROPIC_API_KEY"
            raise LLMUnavailable(self._credential_error) from exc
        except a.PermissionDeniedError as exc:
            raise LLMUnavailable("Claude API key lacks permission") from exc
        except a.RateLimitError as exc:
            raise LLMUnavailable("Claude rate limit reached") from exc
        except a.BadRequestError as exc:
            raise LLMUnavailable(f"Claude rejected the request: {exc.message}") from exc
        except a.APIStatusError as exc:
            raise LLMUnavailable(f"Claude API error {exc.status_code}") from exc
        except a.APITimeoutError as exc:
            raise LLMUnavailable("Claude request timed out") from exc
        except a.APIConnectionError as exc:
            raise LLMUnavailable("Could not reach the Claude API") from exc
        except TypeError as exc:
            # With no credentials configured the SDK raises a plain TypeError
            # while building the request, not an API error.
            if "authentication" in str(exc).lower():
                self._credential_error = "Claude credentials not configured - set ANTHROPIC_API_KEY"
                raise LLMUnavailable(self._credential_error) from exc
            raise LLMUnavailable(f"Claude call failed (TypeError: {exc})"[:300]) from exc
        except Exception as exc:  # noqa: BLE001
            # An unhandled error here would crash the placement run over an
            # optional role.
            raise LLMUnavailable(f"Claude call failed ({type(exc).__name__}: {exc})"[:300]) from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise LLMUnavailable(f"Claude declined the request ({category or 'no category'})")
        if response.stop_reason == "max_tokens":
            raise LLMUnavailable("Claude response was cut off at max_tokens")
        return response

    @staticmethod
    def _first_text(response: Any) -> str:
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise LLMUnavailable("Claude returned no text")
        return text

    async def structured(
        self, *, system: str, prompt: str, schema: dict[str, Any], max_tokens: int = 16000
    ) -> tuple[dict[str, Any], str]:
        response = await self._create(
            system=system,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        try:
            data = json.loads(self._first_text(response))
        except json.JSONDecodeError as exc:
            raise LLMUnavailable("Claude returned invalid JSON") from exc
        return data, response.model

    async def text(
        self, *, system: str, prompt: str, max_tokens: int = 16000
    ) -> tuple[str, str]:
        response = await self._create(
            system=system,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._first_text(response).strip(), response.model
