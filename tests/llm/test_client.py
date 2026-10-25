from __future__ import annotations

import httpx
import pytest

from leichtfacile.llm.cache import ResponseCache
from leichtfacile.llm.client import LLMError, Usage
from tests.conftest import (
    MODEL,
    broken_sse_response,
    chat_response,
    error_response,
    make_settings,
    sse_response,
)

MSG = [{"role": "user", "content": "Hallo"}]


def test_plain_call_returns_text_and_usage(endpoint, make_client):
    endpoint.push(chat_response("Guten Tag.", prompt_tokens=12, completion_tokens=3))
    result = make_client().complete(MSG, stage="understand", temperature=0.1, max_tokens=99)

    assert result.text == "Guten Tag."
    assert result.reasoning is None
    assert result.finish_reason == "stop"
    assert (result.usage.stage, result.usage.model) == ("understand", MODEL)
    assert (result.usage.tokens_in, result.usage.tokens_out) == (12, 3)
    body = endpoint.chat_bodies()[0]
    assert body["model"] == MODEL
    assert body["temperature"] == 0.1
    assert body["max_tokens"] == 99
    assert body["messages"] == MSG


def test_auth_header_carries_the_key(endpoint, make_client):
    endpoint.push(chat_response("ok"))
    make_client().complete(MSG)
    assert endpoint.requests[0].headers["authorization"] == "Bearer test-key"


def test_user_agent_identifies_the_app(endpoint, make_client):
    endpoint.push(chat_response("ok"))
    make_client().complete(MSG)
    make_client().list_models()
    assert all(r.headers["user-agent"].startswith("leicht-facile/") for r in endpoint.requests)


@pytest.mark.parametrize(
    ("requested", "thinking", "expected"),
    [
        (MODEL, True, MODEL + "-thinking"),
        (MODEL, False, MODEL),
        (MODEL + "-thinking", True, MODEL + "-thinking"),
        (MODEL + "-thinking", False, MODEL),
    ],
)
def test_model_suffix_mode(make_client, requested, thinking, expected):
    client = make_client(make_settings(llm__thinking="model-suffix"))
    assert client.resolve_model(requested, thinking) == (expected, {})


def test_chat_template_mode_sends_enable_thinking(endpoint, make_client):
    client = make_client(make_settings(llm__thinking="chat-template"))
    endpoint.push(chat_response("a"), chat_response("b"))
    client.complete(MSG, thinking=True)
    client.complete(MSG, thinking=False)
    first, second = endpoint.chat_bodies()
    assert first["model"] == MODEL
    assert first["chat_template_kwargs"] == {"enable_thinking": True}
    assert second["chat_template_kwargs"] == {"enable_thinking": False}


def test_reasoning_effort_mode_turns_thinking_off_by_request(endpoint, make_client):
    client = make_client(make_settings(llm__thinking="reasoning-effort"))
    endpoint.push(chat_response("a"), chat_response("b"))
    client.complete(MSG, thinking=True)
    client.complete(MSG, thinking=False)
    first, second = endpoint.chat_bodies()
    assert first["model"] == MODEL and "reasoning_effort" not in first  # the model's default
    assert second["reasoning_effort"] == "none"


def test_the_output_budget_field_and_the_temperature_follow_the_endpoint(endpoint, make_client):
    client = make_client(
        make_settings(llm__max_tokens_key="max_completion_tokens", llm__send_temperature=False)
    )
    endpoint.push(chat_response("a"))
    client.complete(MSG, temperature=0.2, max_tokens=500)
    body = endpoint.chat_bodies()[0]
    assert body["max_completion_tokens"] == 500  # OpenAI's GPT-5 models refuse max_tokens
    assert "max_tokens" not in body and "temperature" not in body


def test_extra_body_is_sent_with_every_call(endpoint, make_client):
    client = make_client(
        make_settings(llm__thinking="chat-template", llm__extra_body={"cache": {"no-cache": True}})
    )
    endpoint.push(chat_response("a"))
    client.complete(MSG, thinking=True)
    body = endpoint.chat_bodies()[0]
    assert body["cache"] == {"no-cache": True}
    assert body["chat_template_kwargs"] == {"enable_thinking": True}


def test_off_mode_sends_model_unchanged(endpoint, make_client):
    client = make_client(make_settings(llm__thinking="off"))
    endpoint.push(chat_response("a"))
    client.complete(MSG, thinking=True)
    body = endpoint.chat_bodies()[0]
    assert body["model"] == MODEL
    assert "chat_template_kwargs" not in body


def test_reasoning_from_separate_field(endpoint, make_client):
    endpoint.push(chat_response("42", reasoning_content="17 plus 25 ergibt 42."))
    result = make_client().complete(MSG, thinking=True)
    assert result.text == "42"
    assert result.reasoning == "17 plus 25 ergibt 42."


def test_reasoning_inline_tokens_are_stripped(endpoint, make_client):
    endpoint.push(chat_response("<|inner_prefix|>Ich rechne.<|inner_suffix|>\n42"))
    result = make_client().complete(MSG, thinking=True)
    assert result.text == "42"
    assert result.reasoning == "Ich rechne."


def test_truncated_output_is_flagged(endpoint, make_client):
    endpoint.push(chat_response("<|inner_prefix|>Ich rechne noch", finish_reason="length"))
    result = make_client().complete(MSG, thinking=True)
    assert result.truncated
    assert result.text == ""
    assert result.reasoning == "Ich rechne noch"


def test_retries_on_429_then_succeeds(endpoint, make_client, sleeps):
    endpoint.push(error_response(429), error_response(503), chat_response("ok"))
    result = make_client().complete(MSG)
    assert result.text == "ok"
    assert len(sleeps) == 2
    assert 0.5 <= sleeps[0] <= 1.0  # first backoff 1 s with jitter
    assert 1.0 <= sleeps[1] <= 2.0  # second backoff 2 s with jitter


def test_retry_after_header_is_honoured(endpoint, make_client, sleeps):
    endpoint.push(error_response(429, headers={"retry-after": "7"}), chat_response("ok"))
    make_client().complete(MSG)
    assert sleeps == [7.0]


def test_retries_on_connection_error(endpoint, make_client, sleeps):
    endpoint.push(httpx.ConnectError("refused"), chat_response("ok"))
    assert make_client().complete(MSG).text == "ok"
    assert len(sleeps) == 1


def test_gives_up_after_max_retries(endpoint, make_client, sleeps):
    client = make_client(make_settings(llm__max_retries=2))
    endpoint.push(error_response(500), error_response(500), error_response(500))
    with pytest.raises(LLMError, match="after 3 attempts"):
        client.complete(MSG, stage="write")
    assert len(sleeps) == 2


def test_client_errors_are_not_retried(endpoint, make_client, sleeps):
    endpoint.push(error_response(400))
    with pytest.raises(LLMError, match="rejected"):
        make_client().complete(MSG)
    assert sleeps == []


def test_usage_sink_receives_every_call(endpoint, make_client):
    seen: list[Usage] = []
    endpoint.push(chat_response("a"), chat_response("b"))
    client = make_client(usage_sink=seen.append)
    client.complete(MSG, stage="understand")
    client.complete(MSG, stage="write")
    assert [u.stage for u in seen] == ["understand", "write"]


def test_cache_serves_repeated_calls(endpoint, make_client, tmp_path):
    cache = ResponseCache(tmp_path / "cache.sqlite")
    seen: list[Usage] = []
    client = make_client(cache=cache, usage_sink=seen.append)
    endpoint.push(chat_response("Antwort", reasoning_content="r"))

    first = client.complete(MSG, temperature=0.2)
    second = client.complete(MSG, temperature=0.2)

    assert len(endpoint.chat_bodies()) == 1
    assert (second.text, second.reasoning) == (first.text, first.reasoning)
    assert [u.cached for u in seen] == [False, True]
    cache.close()


def test_cache_key_depends_on_parameters(endpoint, make_client, tmp_path):
    cache = ResponseCache(tmp_path / "cache.sqlite")
    client = make_client(cache=cache)
    endpoint.push(chat_response("a"), chat_response("b"))
    assert client.complete(MSG, temperature=0.0).text == "a"
    assert client.complete(MSG, temperature=0.3).text == "b"
    cache.close()


def test_list_models(make_client):
    assert make_client().list_models() == sorted([MODEL, MODEL + "-thinking"])


def test_judge_defaults_to_writer_model():
    assert make_settings().llm.judge_model == MODEL
    other = "swiss-ai/Apertus-v1.5-70B"
    assert make_settings(llm__models__judge=other).llm.judge_model == other


BIG = "swiss-ai/Apertus-v1.5-70B"


def test_judge_is_the_70b_when_the_endpoint_serves_it():
    # Only the three required settings set: the measured setup.
    settings = make_settings()
    assert settings.llm.larger_model == BIG
    assert settings.llm.judge_for([MODEL, BIG, BIG + "-thinking"]) == BIG
    assert settings.llm.judge_for([MODEL, MODEL + "-thinking"]) == MODEL  # one local model
    assert make_settings(llm__models__judge=MODEL).llm.judge_for([MODEL, BIG]) == MODEL  # as set
    lower = make_settings(llm__models__writer="swiss-ai/apertus-v1.5-8b")  # Public AI's spelling
    assert lower.llm.judge_for(["swiss-ai/apertus-v1.5-70b"]) == "swiss-ai/apertus-v1.5-70b"
    for name in (BIG, "apertus-v1.5-8b-q4-llamacpp", "other-8b"):
        assert make_settings(llm__models__writer=name).llm.larger_model is None


def test_client_looks_the_judge_up_once(endpoint, make_client):
    endpoint.models = [MODEL, BIG]
    client = make_client()
    assert client.judge_model() == BIG
    assert client.judge_model() == BIG
    assert sum(r.url.path.endswith("/models") for r in endpoint.requests) == 1
    # Set explicitly, or no 70B in the family: no lookup at all.
    endpoint.requests.clear()
    assert make_client(make_settings(llm__models__judge=MODEL)).judge_model() == MODEL
    assert make_client(make_settings(llm__models__writer="local-q4")).judge_model() == "local-q4"
    assert not endpoint.requests


def test_judge_falls_back_to_the_writer_while_the_list_fails(endpoint, make_client, monkeypatch):
    endpoint.models = [MODEL, BIG]
    client = make_client()

    def down() -> list[str]:
        raise ConnectionError("down")

    monkeypatch.setattr(client, "list_models", down)
    assert client.judge_model() == MODEL
    monkeypatch.undo()  # the endpoint is back: the next job gets the 70B
    assert client.judge_model() == BIG


def test_understand_defaults_to_writer_model():
    assert make_settings().llm.understand_model == MODEL
    other = "swiss-ai/Apertus-v1.5-70B"
    assert make_settings(llm__models__understand=other).llm.understand_model == other


# -- streaming (the default outside the tests) ----------------------------------------


def test_streaming_collects_text_reasoning_and_usage(endpoint, make_client):
    endpoint.push(
        sse_response("42", reasoning_content="17 plus 25 ergibt 42.", prompt_tokens=12,
                     completion_tokens=3)
    )  # fmt: skip
    client = make_client(make_settings(llm__stream=True))
    result = client.complete(MSG, thinking=True, stage="judge")

    assert result.text == "42"
    assert result.reasoning == "17 plus 25 ergibt 42."
    assert result.finish_reason == "stop"
    assert (result.usage.tokens_in, result.usage.tokens_out) == (12, 3)
    body = endpoint.chat_bodies()[0]
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}


def test_streaming_inline_reasoning_split_across_chunks(endpoint, make_client):
    endpoint.push(sse_response("<|inner_prefix|>Ich rechne.<|inner_suffix|>\n42", pieces=9))
    result = make_client(make_settings(llm__stream=True)).complete(MSG, thinking=True)
    assert result.text == "42"
    assert result.reasoning == "Ich rechne."


def test_streaming_truncation_is_flagged(endpoint, make_client):
    endpoint.push(sse_response("<|inner_prefix|>Ich rechne noch", finish_reason="length"))
    result = make_client(make_settings(llm__stream=True)).complete(MSG, thinking=True)
    assert result.truncated
    assert result.text == ""
    assert result.reasoning == "Ich rechne noch"


def test_streaming_retries_a_gateway_timeout_before_the_first_chunk(endpoint, make_client, sleeps):
    endpoint.push(error_response(504), sse_response("ok"))
    result = make_client(make_settings(llm__stream=True)).complete(MSG)
    assert result.text == "ok"
    assert len(sleeps) == 1


def test_streaming_retries_a_stream_that_breaks(endpoint, make_client, sleeps):
    endpoint.push(broken_sse_response(), sse_response("ok"))
    result = make_client(make_settings(llm__stream=True)).complete(MSG)
    assert result.text == "ok"
    assert len(sleeps) == 1


def test_streaming_without_usage_counts_zero_tokens(endpoint, make_client):
    endpoint.push(sse_response("ok", usage=False))
    result = make_client(make_settings(llm__stream=True)).complete(MSG)
    assert result.text == "ok"
    assert (result.usage.tokens_in, result.usage.tokens_out) == (0, 0)


def test_streaming_results_are_cached(endpoint, make_client, tmp_path):
    cache = ResponseCache(tmp_path / "cache.sqlite")
    client = make_client(make_settings(llm__stream=True), cache=cache)
    endpoint.push(sse_response("Antwort", reasoning_content="r"))
    first = client.complete(MSG)
    second = client.complete(MSG)
    assert len(endpoint.chat_bodies()) == 1
    assert (second.text, second.reasoning, second.usage.cached) == ("Antwort", "r", True)
    assert first.usage.cached is False
    cache.close()
