"""Shared fixtures: settings isolated from the developer's own, and a fake model
endpoint."""

from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from leichtfacile import config
from leichtfacile.config import Settings
from leichtfacile.llm.client import LLMClient


@pytest.fixture(autouse=True)
def _no_user_config(monkeypatch, tmp_path_factory):
    """No test reads the settings of the developer running it: the user's config file
    (`leichtfacile setup`), a leichtfacile.toml or .env in the current folder, or a
    LEICHTFACILE_ variable."""
    none = tmp_path_factory.getbasetemp() / "none"
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(none / "config.toml"))
    monkeypatch.setattr(config, "PROJECT_FILE", none / "leichtfacile.toml")
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", none / ".env")
    for name in list(os.environ):
        if name.upper().startswith(config.ENV_PREFIX) and "__" in name:
            monkeypatch.delenv(name)
    config.use_overrides({})
    yield
    config.use_overrides({})  # the command line's, from a test that runs `main`


BASE_URL = "http://llm.test/v1"
MODEL = "swiss-ai/Apertus-v1.5-8B"


def make_settings(**overrides: Any) -> Settings:
    """Settings for a test: the fake endpoint's, changed by keywords that name a setting
    by its path, with two underscores (`llm__max_retries=0`, `server__host="0.0.0.0"`)."""
    tree: dict[str, Any] = {
        "llm": {
            "url": BASE_URL,
            "api_key": "test-key",
            "models": {"writer": MODEL},
            # The fake endpoint answers with plain JSON; streaming tests switch this on
            # and push `sse_response` bodies instead.
            "stream": False,
            # The fake endpoint plays Apertus on CSCS, which serves thinking as
            # "-thinking" models; the default is off (config.py).
            "thinking": "model-suffix",
        },
        # Never the repository's data/ folder: every test gets a fresh directory.
        "data": {"dir": Path(tempfile.mkdtemp(prefix="leichtfacile-test-"))},
    }
    for key, value in overrides.items():
        *heads, last = key.split("__")
        node = tree
        for head in heads:
            node = node.setdefault(head, {})
        node[last] = value
    return Settings.model_validate(tree)


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
