"""
Language-model providers.

Selected by `LLM_PROVIDER` (auto | anthropic | gemini | none). In this system
an LLM only ever *interprets* findings that other engines established; it
never decides a score, a level or a claim assessment, and its output is
validated before anything shows it (see `investigations/interpret.py`).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from truthshield.providers.base import BaseLLMProvider, LLMResult
from truthshield.providers.resilience import CircuitOpenError

logger = logging.getLogger(__name__)

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5-5"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Server-side refusal fallback: on a safety decline the API re-runs the same
# request on a model chosen per refusal category, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class NullLLMProvider(BaseLLMProvider):
    name = "none"

    def __init__(self, reason: str):
        self._reason = reason

    @property
    def available(self) -> bool:
        return False

    @property
    def unavailable_reason(self) -> Optional[str]:
        return self._reason

    @property
    def model(self) -> str:
        return ""

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4000) -> LLMResult:
        return LLMResult(text=None, model="", provider=self.name, detail=self._reason)


class AnthropicProvider(BaseLLMProvider):
    """Claude through the official SDK, which retries 408/409/429/5xx itself."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str = "", effort: str = "low", timeout: float = 30.0):
        self._key = api_key
        self._model = model or ANTHROPIC_DEFAULT_MODEL
        self._effort = effort
        self._timeout = timeout
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self._key)

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._key, timeout=self._timeout, max_retries=2)
        return self._client

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4000) -> LLMResult:
        import anthropic

        from truthshield.providers.resilience import breaker

        circuit = breaker("llm.anthropic")
        try:
            circuit.before_call()
            response = self._get_client().beta.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                # Thinking is adaptive and always on for this model; effort is
                # the only depth control. Grounded summaries are short.
                output_config={"effort": self._effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
            circuit.record_success()
        except CircuitOpenError as exc:
            return LLMResult(text=None, model=self._model, provider=self.name, detail=str(exc))
        except (anthropic.BadRequestError, anthropic.AuthenticationError,
                anthropic.PermissionDeniedError, anthropic.NotFoundError) as exc:
            # Configuration problems: not retryable, and not a provider outage.
            logger.warning("Anthropic request rejected: %s", type(exc).__name__)
            return LLMResult(text=None, model=self._model, provider=self.name,
                             detail=f"request rejected ({type(exc).__name__})")
        except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            circuit.record_failure()
            logger.warning("Anthropic unavailable: %s", type(exc).__name__)
            return LLMResult(text=None, model=self._model, provider=self.name,
                             detail=f"provider unavailable ({type(exc).__name__})")

        usage = getattr(response, "usage", None)
        result = LLMResult(
            text=None,
            model=getattr(response, "model", self._model),
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
        if response.stop_reason == "refusal":
            result.refused = True
            result.detail = "The model declined this request."
            return result
        result.text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip() or None
        return result


class GeminiProvider(BaseLLMProvider):
    """Gemini over its REST API (no official SDK dependency is installed)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "", timeout: float = 30.0):
        self._key = api_key
        self._model = model or GEMINI_DEFAULT_MODEL
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self._key)

    @property
    def model(self) -> str:
        return self._model

    def complete(self, *, system: str, prompt: str, max_tokens: int = 4000) -> LLMResult:
        import requests

        from truthshield.providers.resilience import call_with_retry

        def call():
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent",
                headers={"x-goog-api-key": self._key, "content-type": "application/json"},
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
                },
                timeout=self._timeout,
            )
            if response.status_code in (429,) or response.status_code >= 500:
                raise ConnectionError(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response.json()

        try:
            body = call_with_retry(call, name="llm.gemini", attempts=3,
                                   retry_on=(ConnectionError, TimeoutError, requests.Timeout, requests.ConnectionError))
        except Exception as exc:
            return LLMResult(text=None, model=self._model, provider=self.name,
                             detail=f"provider unavailable ({type(exc).__name__})")

        usage = body.get("usageMetadata") or {}
        candidates = body.get("candidates") or []
        if candidates and candidates[0].get("finishReason") == "SAFETY":
            return LLMResult(text=None, model=self._model, provider=self.name, refused=True,
                             detail="The model declined this request.")
        parts = (candidates[0].get("content", {}).get("parts") if candidates else None) or []
        return LLMResult(
            text="".join(p.get("text", "") for p in parts).strip() or None,
            model=self._model,
            provider=self.name,
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
        )


@lru_cache
def get_llm_provider() -> BaseLLMProvider:
    from truthshield.settings import get_settings

    s = get_settings()
    choice = s.LLM_PROVIDER.strip().lower()
    if choice == "none":
        return NullLLMProvider("LLM_PROVIDER is set to none.")
    if s.OFFLINE_MODE:
        return NullLLMProvider("Offline mode: no language model is called.")

    candidates = {
        "anthropic": lambda: AnthropicProvider(s.ANTHROPIC_API_KEY, s.LLM_MODEL, s.LLM_EFFORT, s.LLM_TIMEOUT_SECONDS),
        "gemini": lambda: GeminiProvider(s.GEMINI_API_KEY, s.LLM_MODEL, s.LLM_TIMEOUT_SECONDS),
    }
    if choice in candidates:
        provider = candidates[choice]()
        return provider if provider.available else NullLLMProvider(
            f"LLM_PROVIDER={choice} but its API key is not configured."
        )
    for name in ("anthropic", "gemini"):
        provider = candidates[name]()
        if provider.available:
            return provider
    return NullLLMProvider("No LLM API key is configured.")


def reset_llm_provider() -> None:
    get_llm_provider.cache_clear()
