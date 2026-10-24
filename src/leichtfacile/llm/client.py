"""One client for every model endpoint: Apertus on CSCS or Public AI, a local vLLM,
llama.cpp or Ollama server, a Swiss cloud or another provider.

All of them speak the OpenAI chat-completions protocol, so the deployment target is a
matter of configuration (`llm.url`, `llm.api_key`, `llm.models.writer`). This module adds
what the pipeline needs on top of the SDK: thinking-mode handling, reasoning removal,
streaming (so that a proxy in front of the endpoint cannot time out a long answer),
retries with backoff, a usage record per call and an optional response cache.

Privacy: document text is never logged above DEBUG. Log lines carry model, stage,
token counts and latency only.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, Literal

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
# Where the calls of the current thread are billed, set by `LLMClient.recording`.
_RECORDING: ContextVar[Callable[[Usage], None] | None] = ContextVar("llm_recording", default=None)
# The time budget and the stop signal of the job the current thread runs, set by
# `LLMClient.limited`; checked before every attempt and on every streamed chunk.
_LIMIT: ContextVar[RunLimit | None] = ContextVar("llm_limit", default=None)


class LLMError(RuntimeError):
    """The endpoint failed after all retries, or rejected the request."""


class LLMInterrupted(RuntimeError):
    """The call was abandoned because the job was stopped (`cancelled`) or its time
    budget ran out (`budget`). Not an `LLMError`: a stage never treats it as a failure
    of the endpoint and carries on."""

    def __init__(self, reason: Literal["cancelled", "budget"]) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class RunLimit:
    """What ends a job early: a deadline on the monotonic clock and a stop event."""

    deadline: float | None = None
    stop: threading.Event | None = None
    clock: Callable[[], float] = time.monotonic

    def check(self) -> None:
        if self.stop is not None and self.stop.is_set():
            raise LLMInterrupted("cancelled")
        if self.deadline is not None and self.clock() >= self.deadline:
            raise LLMInterrupted("budget")

    def remaining(self) -> float | None:
        return None if self.deadline is None else max(0.0, self.deadline - self.clock())


def check_limit() -> None:
    """Raise `LLMInterrupted` when the current thread's job was stopped or is over its
    time budget; nothing happens outside `LLMClient.limited`."""
    limit = _LIMIT.get()
    if limit is not None:
        limit.check()


@dataclass(frozen=True)
class Usage:
    stage: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool = False
    cache_key: str | None = None  # the response cache's key, when the cache is on


@dataclass(frozen=True)
class LLMResult:
    text: str
    reasoning: str | None
    finish_reason: str | None
    usage: Usage
    cache_key: str | None = None  # set when a response cache is on (see `forget`)

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
        self._judge_model: str | None = None
        self._client = openai.OpenAI(
            base_url=settings.llm.url,
            api_key=settings.llm.api_key.get_secret_value() if settings.llm.api_key else "none",
            timeout=settings.llm.timeout_s,
            max_retries=0,  # retries are handled here, with logging and Retry-After support
            default_headers={"User-Agent": USER_AGENT},
            http_client=http_client,
        )

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> LLMClient:
        if settings.llm.cache and "cache" not in kwargs:
            kwargs["cache"] = ResponseCache(settings.data.dir / "llm_cache.sqlite")
        return cls(settings, **kwargs)

    @property
    def cache(self) -> ResponseCache | None:
        """The response cache, shared with the clients of the other endpoints."""
        return self._cache

    # -- model resolution -------------------------------------------------------------

    def resolve_model(self, model: str | None, thinking: bool) -> tuple[str, dict[str, Any]]:
        """Return the model name to send and any extra request body for thinking mode."""
        name = model or self.settings.llm.models.writer
        mode = self.settings.llm.thinking
        suffix = self.settings.llm.thinking_suffix
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
        extra_body = {**self.settings.llm.extra_body, **thinking_body}
        params: dict[str, Any] = {"temperature": temperature, "max_tokens": max_tokens}
        if response_format:
            params["response_format"] = response_format
        if extra_body:
            params["extra_body"] = extra_body

        check_limit()
        key = cache_key(name, messages, params) if self._cache else None
        hit = self._cache.get(key) if self._cache and key else None
        if hit is not None:
            usage = Usage(
                stage, name, hit["tokens_in"], hit["tokens_out"], 0, cached=True, cache_key=key
            )
            self._record(usage)
            return LLMResult(
                hit["text"], hit["reasoning"], hit["finish_reason"], usage, cache_key=key
            )

        started = time.perf_counter()
        reply = self._create_with_retries(name, messages, params, stage)
        latency_ms = int((time.perf_counter() - started) * 1000)

        answer, inline_reasoning = split_reasoning(reply.content)
        reasoning = "\n\n".join(r for r in (reply.reasoning, inline_reasoning) if r) or None

        usage = Usage(stage, name, reply.tokens_in, reply.tokens_out, latency_ms, cache_key=key)
        self._record(usage)
        if reply.finish_reason == "length":
            log.warning(
                "LLM output truncated (stage=%s, model=%s, max_tokens=%d)",
                stage,
                name,
                max_tokens,
            )

        result = LLMResult(answer, reasoning, reply.finish_reason, usage, cache_key=key)
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

    def forget(self, result: LLMResult) -> None:
        """Drop a response from the cache: an answer that could not be used (no valid
        JSON, a copy of the prompt's example) must not be served again on a rerun; the
        evaluation reruns failed pairs with the cache on."""
        if self._cache and result.cache_key:
            self._cache.delete(result.cache_key)

    def forget_keys(self, keys: list[str]) -> int:
        """Drop these responses from the cache: a deleted job takes its prompts, which
        carry the document, with it (`Store.cache_keys`). The number dropped."""
        if not self._cache:
            return 0
        for key in keys:
            self._cache.delete(key)
        return len(keys)

    def list_models(self, timeout_s: float = 10.0) -> list[str]:
        page = self._client.with_options(timeout=timeout_s).models.list()
        return sorted(m.id for m in page)

    def judge_model(self) -> str:
        """The judge's model (`Settings.judge_for`). The endpoint's list is asked once,
        and only when it decides; while it cannot be read, the writer's model judges."""
        settings = self.settings
        if settings.llm.models.judge or not settings.llm.larger_model:
            return settings.llm.judge_model
        if self._judge_model is None:
            try:
                models = self.list_models()
            except Exception as exc:  # the judge still runs, on the writer's model
                log.warning("model list for the judge failed: %s", type(exc).__name__)
                return settings.llm.models.writer
            self._judge_model = settings.llm.judge_for(models)
            log.info("judge model: %s", self._judge_model)
        return self._judge_model

    # -- internals --------------------------------------------------------------------

    def _create_with_retries(
        self, name: str, messages: list[Message], params: dict[str, Any], stage: str
    ) -> _Reply:
        attempts = self.settings.llm.max_retries + 1
        for attempt in range(1, attempts + 1):
            check_limit()
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
        limit = _LIMIT.get()
        remaining = limit.remaining() if limit else None
        if remaining is not None:
            delay = min(delay, remaining)  # the next check raises once the budget is out
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
        """One request, streamed unless `llm.stream = false`.

        Streaming makes the endpoint send the answer as it is generated, so a proxy in
        front of it (Cloudflare in front of the Public AI gateway cuts a response after
        about 100 seconds) never waits for a long answer. The token counts come with the
        last chunk (`stream_options.include_usage`).
        """
        if not self.settings.llm.stream:
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
                check_limit()  # a stopped job abandons the stream at the next chunk
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

    @contextmanager
    def recording(self, sink: Callable[[Usage], None]) -> Iterator[None]:
        """Pass every call made in this thread inside the block to `sink` as it is made.
        The orchestrator bills a job this way: a stage that fails after two calls has
        made them, though it returns no results (a failed Understand reported 0 calls,
        7 October 2026)."""
        token = _RECORDING.set(sink)
        try:
            yield
        finally:
            _RECORDING.reset(token)

    @contextmanager
    def limited(self, limit: RunLimit) -> Iterator[None]:
        """End the calls made in this thread inside the block early when the job is
        stopped or over its time budget: `LLMInterrupted` before the next attempt, at
        the next streamed chunk, and after a backoff. The orchestrator runs every job
        inside one."""
        token = _LIMIT.set(limit)
        try:
            yield
        finally:
            _LIMIT.reset(token)

    def _record(self, usage: Usage) -> None:
        log.info("llm_call %s", asdict(usage))
        if self._usage_sink:
            self._usage_sink(usage)
        if (sink := _RECORDING.get()) is not None:
            sink(usage)


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
