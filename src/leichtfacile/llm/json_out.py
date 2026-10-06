"""Structured output without relying on server-side JSON mode.

Neither the CSCS documentation nor the vLLM guide promises `response_format`, so JSON
is enforced the robust way: the schema goes into the prompt, the answer is stripped of
reasoning and code fences, the first JSON value is parsed, and pydantic validates it.
On failure the error is fed back to the model once for a repair.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from leichtfacile.llm.client import LLMClient, LLMResult, Message
from leichtfacile.llm.reasoning import split_reasoning

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.DOTALL)
_MAX_ERROR_CHARS = 2000


class JSONExtractionError(ValueError):
    """No JSON value could be parsed from the model's answer."""


class LLMOutputError(RuntimeError):
    """The model's answer did not validate, even after the repair round."""

    def __init__(self, message: str, results: list[LLMResult]) -> None:
        super().__init__(message)
        self.results = results


def extract_json(text: str) -> Any:
    """Parse the first JSON object or array in a model answer."""
    answer, _ = split_reasoning(text)
    candidates = [m.group(1) for m in _FENCE.finditer(answer)] + [answer]
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for i, ch in enumerate(candidate):
            if ch not in "{[":
                continue
            try:
                value, _ = decoder.raw_decode(candidate, i)
            except json.JSONDecodeError:
                continue
            return value
    raise JSONExtractionError("no JSON object or array found in the model answer")


def schema_instruction(schema: type[BaseModel]) -> str:
    """Prompt text that tells the model which JSON to return."""
    return (
        "Answer with one JSON object only, no other text. "
        "It must validate against this JSON schema:\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
    )


def complete_json[T: BaseModel](
    client: LLMClient,
    messages: list[Message],
    schema: type[T],
    *,
    max_repairs: int = 1,
    **kwargs: Any,
) -> tuple[T, list[LLMResult]]:
    """Call the model and return a validated instance of `schema` plus all raw results."""
    conversation = list(messages)
    results: list[LLMResult] = []
    for attempt in range(max_repairs + 1):
        result = client.complete(conversation, **kwargs)
        results.append(result)
        if result.truncated:
            # A cut-off answer still contains complete inner objects that would parse;
            # it is never used, and asking again for the same answer does not help.
            raise LLMOutputError(
                f"model output for {schema.__name__} was cut off at max_tokens", results
            )
        try:
            return schema.model_validate(extract_json(result.text)), results
        except (JSONExtractionError, ValidationError) as exc:
            error = str(exc)[:_MAX_ERROR_CHARS]
            if attempt == max_repairs:
                raise LLMOutputError(
                    f"model output did not validate as {schema.__name__}: {error}", results
                ) from exc
            conversation = [
                *conversation,
                {"role": "assistant", "content": result.text},
                {
                    "role": "user",
                    "content": "Your answer could not be used. Error:\n"
                    + error
                    + "\nReturn the corrected JSON object only, no other text.",
                },
            ]
    raise AssertionError("unreachable")
