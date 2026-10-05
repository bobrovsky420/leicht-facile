"""Shared fixtures: settings isolated from the local .env, and a fake model endpoint."""

from __future__ import annotations

import json
from collections.abc import Callable
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
    """Records requests and answers chat calls from a queue."""

    def __init__(self, models: list[str] | None = None) -> None:
        self.models = models if models is not None else [MODEL, MODEL + "-thinking"]
        self.queue: list[httpx.Response | Exception] = []
        self.requests: list[httpx.Request] = []

    def push(self, *responses: httpx.Response | Exception) -> None:
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
