"""Shared fixtures: settings isolated from the local .env, and a fake model endpoint."""

from __future__ import annotations

import json
import math
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from leichtfacile.config import Settings
from leichtfacile.llm.client import LLMClient

BASE_URL = "http://llm.test/v1"
MODEL = "swiss-ai/Apertus-v1.5-8B"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "llm_base_url": BASE_URL,
        "llm_api_key": "test-key",
        "llm_name": MODEL,
        # The fake endpoint answers with plain JSON; streaming tests switch this on and
        # push `sse_response` bodies instead.
        "llm_stream": False,
        # Never the repository's data/ folder: every test gets a fresh directory.
        "data_dir": Path(tempfile.mkdtemp(prefix="leichtfacile-test-")),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def chat_response(
    content: str | None,
    *,
    reasoning_content: str | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 11,
    completion_tokens: int = 7,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    body = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return httpx.Response(status, json=body, headers=headers)


def error_response(status: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": f"error {status}"}}, headers=headers)


class FakeEndpoint:
    """Records requests and answers chat calls from a queue: a response, an exception
    to raise, or a function of the request that returns the response (a test can let
    it wait on an event to hold the call)."""

    def __init__(self, models: list[str] | None = None) -> None:
        self.models = models if models is not None else [MODEL, MODEL + "-thinking"]
        self.queue: list[httpx.Response | Exception | Callable[..., httpx.Response]] = []
        self.requests: list[httpx.Request] = []

    def push(self, *responses: httpx.Response | Exception | Callable[..., httpx.Response]) -> None:
        self.queue.extend(responses)

    def chat_bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path.endswith("/completions")]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/models"):
            data = [
                {"id": m, "object": "model", "created": 0, "owned_by": "test"} for m in self.models
            ]
            return httpx.Response(200, json={"object": "list", "data": data})
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(request)
        return item

    def http_client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


@pytest.fixture
def endpoint() -> FakeEndpoint:
    return FakeEndpoint()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def make_client(endpoint: FakeEndpoint, sleeps: list[float]) -> Callable[..., LLMClient]:
    def factory(settings: Settings | None = None, **kwargs: Any) -> LLMClient:
        return LLMClient(
            settings or make_settings(),
            http_client=endpoint.http_client(),
            sleep=sleeps.append,
            **kwargs,
        )

    return factory


def _pieces(text: str, count: int) -> list[str]:
    size = max(1, math.ceil(len(text) / count))
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


def _chunk(delta: dict[str, Any], finish_reason: str | None = None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": MODEL,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def sse_response(
    content: str | None,
    *,
    reasoning_content: str | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 11,
    completion_tokens: int = 7,
    usage: bool = True,
    pieces: int = 3,
) -> httpx.Response:
    """A streamed chat completion: reasoning and text in a few chunks, the finish
    reason, then the usage chunk that `stream_options.include_usage` asks for."""
    events = []
    if reasoning_content:
        events += [_chunk({"reasoning_content": p}) for p in _pieces(reasoning_content, pieces)]
    events += [_chunk({"content": p}) for p in _pieces(content or "", pieces)]
    events.append(_chunk({}, finish_reason))
    if usage:
        events.append(
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": MODEL,
                "choices": [],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
        )
    body = "".join(f"data: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events)
    return httpx.Response(
        200, content=(body + "data: [DONE]\n\n").encode("utf-8"),
        headers={"content-type": "text/event-stream"},
    )  # fmt: skip


class _BrokenStream(httpx.SyncByteStream):
    """A response body that breaks after its first chunk: the connection dropped."""

    def __init__(self, head: bytes) -> None:
        self.head = head

    def __iter__(self):
        yield self.head
        raise httpx.ReadError("connection lost")


def broken_sse_response() -> httpx.Response:
    head = f"data: {json.dumps(_chunk({'content': 'Teil'}))}\n\n".encode()
    return httpx.Response(
        200, stream=_BrokenStream(head), headers={"content-type": "text/event-stream"}
    )
