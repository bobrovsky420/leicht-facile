"""One client for every Apertus endpoint: CSCS, local vLLM, Swiss cloud, Hugging Face.

All of them speak the OpenAI chat-completions protocol, so the deployment target is a
matter of configuration (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_NAME`). This module adds
what the pipeline needs on top of the SDK: thinking-mode handling, reasoning removal,
streaming (so that a proxy in front of the endpoint cannot time out a long answer),
retries with backoff, a usage record per call and an optional response cache.

Privacy: document text is never logged above DEBUG. Log lines carry model, stage,
token counts and latency only.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import httpx
import openai

from leichtfacile import __version__
from leichtfacile.config import Settings
from leichtfacile.llm.cache import ResponseCache, cache_key
from leichtfacile.llm.reasoning import split_reasoning

log = logging.getLogger(__name__)

Message = dict[str, Any]

_RETRYABLE = (
    openai.RateLimitError,
    openai.InternalServerError,
    openai.APIConnectionError,  # includes APITimeoutError
    httpx.HTTPError,  # a stream that breaks after the headers arrived
    httpx.StreamError,
)
_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 30.0
# Some gateways (Public AI) reject requests without an identifying User-Agent.
USER_AGENT = f"leicht-facile/{__version__}"


class LLMError(RuntimeError):
    """The endpoint failed after all retries, or rejected the request."""


@dataclass(frozen=True)
class Usage:
    stage: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool = False


@dataclass(frozen=True)
class LLMResult:
    text: str
    reasoning: str | None
    finish_reason: str | None
    usage: Usage

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


@dataclass(frozen=True)
class _Reply:
    """What a chat completion contains, the same for a streamed and a plain response."""

    content: str
    reasoning: str | None  # from a separate field of the response, if the server has one
    finish_reason: str | None
    tokens_in: int
    tokens_out: int


class LLMClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        cache: ResponseCache | None = None,
        usage_sink: Callable[[Usage], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._cache = cache
        self._usage_sink = usage_sink
        self._sleep = sleep
        self._warned_no_usage = False
        self._client = openai.OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=settings.llm_timeout_s,
            max_retries=0,  # retries are handled here, with logging and Retry-After support
            default_headers={"User-Agent": USER_AGENT},
            http_client=http_client,
        )

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> LLMClient:
        if settings.llm_cache and "cache" not in kwargs:
            kwargs["cache"] = ResponseCache(settings.data_dir / "llm_cache.sqlite")
        return cls(settings, **kwargs)

    # -- model resolution -------------------------------------------------------------

    def resolve_model(self, model: str | None, thinking: bool) -> tuple[str, dict[str, Any]]:
        """Return the model name to send and any extra request body for thinking mode."""
        name = model or self.settings.llm_name
        mode = self.settings.llm_thinking_mode
        suffix = self.settings.llm_thinking_suffix
        if mode == "model-suffix":
            if thinking and not name.endswith(suffix):
                name += suffix
            elif not thinking and name.endswith(suffix):
                name = name[: -len(suffix)]
            return name, {}
        if mode == "chat-template":
            return name, {"chat_template_kwargs": {"enable_thinking": thinking}}
        return name, {}

    # -- calls ------------------------------------------------------------------------

    def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        thinking: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        stage: str = "adhoc",
        response_format: dict[str, Any] | None = None,
    ) -> LLMResult:
        name, thinking_body = self.resolve_model(model, thinking)
        extra_body = {**self.settings.llm_extra_body, **thinking_body}
        params: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens}
        if response_format:
            params["response_format"] = response_format
        if extra_body:
            params["extra_body"] = extra_body

        key = cache_key(name, messages, params) if self._cache else None
        if self._cache and key:
            hit = self._cache.get(key)
            if hit is not None:
                usage = Usage(stage, name, hit["tokens_in"], hit["tokens_out"], 0, cached=True)
                self._record(usage)
                return LLMResult(hit["text"], hit["reasoning"], hit["finish_reason"], usage)

        started = time.perf_counter()
        reply = self._create_with_retries(name, messages, params, stage)
        latency_ms = int((time.perf_counter() - started) * 1000)

        answer, inline_reasoning = split_reasoning(reply.content)
        reasoning = "\n\n".join(r for r in (reply.reasoning, inline_reasoning) if r) or None

        usage = Usage(stage, name, reply.tokens_in, reply.tokens_out, latency_ms)
        self._record(usage)
        if reply.finish_reason == "length":
            log.warning(
                "LLM output truncated (stage=%s, model=%s, max_tokens=%d)",
                stage,
                name,
                max_tokens,
            )

        result = LLMResult(answer, reasoning, reply.finish_reason, usage)
        if self._cache and key:
            self._cache.put(
                key,
                name,
                {
                    "text": answer,
                    "reasoning": reasoning,
                    "finish_reason": reply.finish_reason,
                    "tokens_in": reply.tokens_in,
                    "tokens_out": reply.tokens_out,
                },
            )
        return result

    def list_models(self, timeout_s: float = 10.0) -> list[str]:
        page = self._client.with_options(timeout=timeout_s).models.list()
        return sorted(m.id for m in page)

    # -- internals --------------------------------------------------------------------

    def _create_with_retries(
        self, name: str, messages: list[Message], params: dict[str, Any], stage: str
    ) -> _Reply:
        attempts = self.settings.llm_max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                return self._request(name, messages, params)
            except _RETRYABLE as exc:
                self._retry_or_raise(exc, attempt, attempts, name, stage)
            except openai.APIStatusError as exc:
                raise LLMError(
                    f"LLM request rejected (stage={stage}, model={name}): {_describe(exc)}"
                ) from exc
            except openai.APIError as exc:
                # An error event inside a stream (a gateway reporting an upstream
                # failure): retried like a 5xx.
                self._retry_or_raise(exc, attempt, attempts, name, stage)
        raise AssertionError("unreachable")

    def _retry_or_raise(
        self, exc: Exception, attempt: int, attempts: int, name: str, stage: str
    ) -> None:
        if attempt == attempts:
            raise LLMError(
                f"LLM call failed after {attempts} attempts "
                f"(stage={stage}, model={name}): {_describe(exc)}"
            ) from exc
        delay = _retry_delay(exc, attempt)
        log.warning(
            "LLM call failed (stage=%s, model=%s, attempt %d/%d): %s; retrying in %.1fs",
            stage,
            name,
            attempt,
            attempts,
            _describe(exc),
            delay,
        )
        self._sleep(delay)

    def _request(self, name: str, messages: list[Message], params: dict[str, Any]) -> _Reply:
        """One request, streamed unless `LLM_STREAM=0`.

        Streaming makes the endpoint send the answer as it is generated, so a proxy in
        front of it (Cloudflare in front of the Public AI gateway cuts a response after
        about 100 seconds) never waits for a long answer. The token counts come with the
        last chunk (`stream_options.include_usage`).
        """
        if not self.settings.llm_stream:
            response = self._client.chat.completions.create(
                model=name,
                messages=messages,  # type: ignore[arg-type]
                **params,
            )
            choice = response.choices[0]
            return _Reply(
                choice.message.content or "",
                _reasoning_field(choice.message),
                choice.finish_reason,
                getattr(response.usage, "prompt_tokens", 0) or 0,
                getattr(response.usage, "completion_tokens", 0) or 0,
            )

        content: list[str] = []
        reasoning: list[str] = []
        finish_reason: str | None = None
        tokens_in = tokens_out = 0
        saw_usage = False
        stream = self._client.chat.completions.create(
            model=name,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
            stream_options={"include_usage": True},
            **params,
        )
        with stream:
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    tokens_in = getattr(usage, "prompt_tokens", 0) or 0
                    tokens_out = getattr(usage, "completion_tokens", 0) or 0
                    saw_usage = True
                for choice in chunk.choices or []:
                    delta = choice.delta
                    if delta is not None:
                        if delta.content:
                            content.append(delta.content)
                        piece = _reasoning_piece(delta)
                        if piece:
                            reasoning.append(piece)
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
        if not saw_usage and not self._warned_no_usage:
            self._warned_no_usage = True
            log.warning("the endpoint sends no usage with its streams; token counts are 0")
        return _Reply(
            "".join(content),
            "".join(reasoning).strip() or None,
            finish_reason,
            tokens_in,
            tokens_out,
        )

    def _record(self, usage: Usage) -> None:
        log.info("llm_call %s", asdict(usage))
        if self._usage_sink:
            self._usage_sink(usage)


def _reasoning_field(message: Any) -> str | None:
    extra = getattr(message, "model_extra", None) or {}
    for field in ("reasoning_content", "reasoning"):
        value = extra.get(field) or getattr(message, field, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _reasoning_piece(delta: Any) -> str:
    """The reasoning in one streamed chunk, unstripped: the pieces are joined later."""
    extra = getattr(delta, "model_extra", None) or {}
    for field in ("reasoning_content", "reasoning"):
        value = extra.get(field)
        if value is None:
            value = getattr(delta, field, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _retry_delay(exc: Exception, attempt: int) -> float:
    response = getattr(exc, "response", None)
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), _BACKOFF_MAX_S)
            except ValueError:
                pass
    backoff = min(_BACKOFF_BASE_S * 2 ** (attempt - 1), _BACKOFF_MAX_S)
    return backoff * (0.5 + random.random() / 2)  # jitter: 50-100 percent of the backoff


def _describe(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    if status:
        return f"{name} {status}"
    cause = exc.__cause__  # a connection error wraps the transport error that says why
    if cause is not None:
        return f"{name} ({type(cause).__name__}: {str(cause)[:80]})"
    return name
