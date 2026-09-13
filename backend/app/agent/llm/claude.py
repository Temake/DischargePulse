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
import re
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


# Bedrock has two integrations with different model IDs and clients:
#   - Messages-API endpoint (newer models): `anthropic.claude-opus-5`
#   - legacy InvokeModel (Opus 4.6 and earlier, e.g. Sonnet 4.5): inference
#     profile IDs like `global.anthropic.claude-sonnet-4-5-20250929-v1:0`
_LEGACY_BEDROCK_ID = re.compile(r"^(global|us|eu|jp|apac)\.anthropic\.|-v\d+(:\d+)?$")


def bedrock_uses_legacy(model: str) -> bool:
    return bool(_LEGACY_BEDROCK_ID.search(model))


def bedrock_model_id(model: str) -> str:
    """The model ID as Bedrock expects it for the integration it belongs to."""
    if bedrock_uses_legacy(model) or model.startswith("anthropic."):
        return model
    return f"anthropic.{model}"


class ClaudeBackend:
    """`LLMBackend` over the Claude Messages API, first-party or on Bedrock."""

    def __init__(
        self,
        model: str,
        timeout_seconds: float,
        client: Any = None,
        provider: str = "anthropic",
        aws_region: str | None = None,
        fallback_model: str | None = None,
    ) -> None:
        import anthropic

        self._anthropic = anthropic
        self.provider = provider

        if provider == "bedrock" and bedrock_uses_legacy(model):
            # Legacy InvokeModel integration (e.g. Sonnet 4.5). Server-side
            # fallbacks are unavailable and no client-side fallback is applied,
            # so a refusal surfaces as LLMUnavailable.
            self.model = model
            self._request_extras: dict[str, Any] = {}
            self._use_beta = False
            self._client = client or anthropic.AsyncAnthropicBedrock(
                aws_region=aws_region, timeout=timeout_seconds, max_retries=2
            )
        elif provider == "bedrock":
            self.model = bedrock_model_id(model)
            # Bedrock rejects the server-side `fallbacks` parameter; the SDK's
            # client-side middleware retries a refusal on the fallback model.
            middleware = (
                [anthropic.BetaRefusalFallbackMiddleware([{"model": bedrock_model_id(fallback_model)}])]
                if fallback_model
                else None
            )
            self._request_extras = {}
            self._use_beta = True
            self._client = client or anthropic.AsyncAnthropicBedrockMantle(
                aws_region=aws_region,
                timeout=timeout_seconds,
                max_retries=2,
                middleware=middleware,
            )
        elif provider == "anthropic":
            self.model = model
            self._request_extras = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
            self._use_beta = True
            self._client = client or anthropic.AsyncAnthropic(
                timeout=timeout_seconds, max_retries=2
            )
        else:
            raise ValueError(f"Unknown LLM provider '{provider}' (use anthropic or bedrock)")
        # Set once credentials are known to be missing or rejected, so a run
        # does not retry - and log - the same failure for every facility.
        self._credential_error: str | None = None

    async def _create(self, **kwargs: Any) -> Any:
        if self._credential_error:
            raise LLMUnavailable(self._credential_error)
        a = self._anthropic
        try:
            messages_api = self._client.beta.messages if self._use_beta else self._client.messages
            response = await messages_api.create(
                model=self.model,
                **self._request_extras,
                **kwargs,
            )
        except a.AuthenticationError as exc:
            self._credential_error = f"Claude credentials invalid - check {self._credential_hint}"
            raise LLMUnavailable(self._credential_error) from exc
        except a.PermissionDeniedError as exc:
            # On Bedrock this usually means model access is not enabled for the
            # account and region.
            raise LLMUnavailable(
                "Bedrock denied access - enable this Claude model for the account and region"
                if self.provider == "bedrock"
                else "Claude API key lacks permission"
            ) from exc
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
                self._credential_error = f"Claude credentials not configured - set {self._credential_hint}"
                raise LLMUnavailable(self._credential_error) from exc
            raise LLMUnavailable(f"Claude call failed (TypeError: {exc})"[:300]) from exc
        except RuntimeError as exc:
            # Bedrock with no AWS credentials raises a plain RuntimeError.
            if "credentials" in str(exc).lower():
                self._credential_error = f"Claude credentials not configured - set {self._credential_hint}"
                raise LLMUnavailable(self._credential_error) from exc
            raise LLMUnavailable(f"Claude call failed (RuntimeError: {exc})"[:300]) from exc
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

    @property
    def _credential_hint(self) -> str:
        if self.provider == "bedrock":
            return "AWS_BEARER_TOKEN_BEDROCK or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, plus AWS_REGION"
        return "ANTHROPIC_API_KEY"

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
