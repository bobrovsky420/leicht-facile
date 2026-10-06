"""Structured output without relying on server-side JSON mode.

Neither the CSCS documentation nor the vLLM guide promises `response_format`, so JSON
is enforced the robust way: the schema goes into the prompt, the answer is stripped of
reasoning and code fences, the first JSON value is parsed, and pydantic validates it.
On failure the error is fed back to the model once for a repair.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from leichtfacile.llm.client import LLMClient, LLMResult, Message
from leichtfacile.llm.reasoning import split_reasoning

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.DOTALL)
_MAX_ERROR_CHARS = 2000
_KEY = re.compile(r'"\s*:')  # a key: the value that broke was the answer, not prose
# Slips of a small model in otherwise well-formed JSON. On long pages the 8B abbreviates
# a run of ids as a range ("s0064" bis "s0087", "s0045" ... "s0057"), which JSON has no
# syntax for; the list is written out. Range markers: ..., the ellipsis, a hyphen or an
# en dash (as escapes), bis, to, à.
_ID_RANGE = re.compile(
    r"""
    "([a-z]{1,2})(\d{2,4})"            # the first id: prefix and number
    \s*(?:\.\.\.|\u2026|\u2013|-|bis|to|à|jusqu'à)\s*
    "\1(\d{2,4})"                      # the last id, same prefix
    """,
    re.VERBOSE,
)
_MAX_RANGE = 500
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_MISSING_COMMA_OBJECTS = re.compile(r"}\s*\n(\s*){")
# A value (closing quote, bracket or brace) followed by the next key without a comma,
# on the same line or the next ("s0095"] "must_keep": ...).
_MISSING_COMMA_KEYS = re.compile(r'([\]}"])(\s+)("[A-Za-z_]\w*"\s*:)')
# A German quotation inside a string closed with a straight quote („muss zeigen"), which
# ends the JSON string early; the closing quote becomes the German one.
_LOW_QUOTE = re.compile('\u201e([^"\n]{1,120})"')
_KEY_AT = re.compile(r'"([A-Za-z_]\w*)"\s*:')
# A list that belongs at the top level, written as a pseudo-block inside "blocks"
# ({"kind": "omissions": [...]}): the key is restored here and WriteOut hoists the list.
_NESTED_LIST = re.compile(r'\{\s*"kind"\s*:\s*"(omissions|glossary)"\s*:\s*\[')


class JSONExtractionError(ValueError):
    """No JSON value could be parsed from the model's answer."""


class LLMOutputError(RuntimeError):
    """The model's answer did not validate, even after the repair round."""

    def __init__(self, message: str, results: list[LLMResult]) -> None:
        super().__init__(message)
        self.results = results


def _expand_range(m: re.Match[str]) -> str:
    prefix, first, last = m.group(1), m.group(2), m.group(3)
    lo, hi = int(first), int(last)
    if hi < lo or hi - lo > _MAX_RANGE:
        return m.group(0)
    return ", ".join(f'"{prefix}{n:0{len(first)}d}"' for n in range(lo, hi + 1))


def repair_json(text: str, top_keys: Iterable[str] = ()) -> str:
    """Fix the slips of small models in otherwise well-formed JSON (see the patterns)."""
    text = _ID_RANGE.sub(_expand_range, text)
    text = _TRAILING_COMMA.sub(r"\1", text)
    text = _MISSING_COMMA_OBJECTS.sub(r"},\n\1{", text)
    text = _NESTED_LIST.sub(r'{"\1": [', text)
    text = _LOW_QUOTE.sub("\u201e\\1\u201c", text)
    text = _MISSING_COMMA_KEYS.sub(r"\1,\2\3", text)
    return close_containers(text, top_keys)


def close_containers(text: str, top_keys: Iterable[str]) -> str:
    """Close the objects and lists a model forgot to close before a top-level key.

    `{"core": {"what": {...}, "facts": [...]}` lacks the brace that ends `core`; the
    answer's top-level keys (the schema's fields) show where it belongs.
    """
    keys = set(top_keys)
    if not keys:
        return text
    out: list[str] = []
    stack: list[str] = []
    in_string = escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            m = _KEY_AT.match(text, i)
            if m and m.group(1) in keys and len(stack) > 1:
                closers = "".join("}" if o == "{" else "]" for o in reversed(stack[1:]))
                j = len(out) - 1
                while j >= 0 and out[j].isspace():
                    j -= 1
                if j >= 0 and out[j] == ",":
                    out.insert(j, closers)  # before the comma that already separates
                else:
                    out.insert(j + 1, closers + ",")
                del stack[1:]
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()
        out.append(ch)
        i += 1
    return "".join(out)


def _near(text: str, pos: int) -> str:
    window = text[max(0, pos - 60) : pos] + " <<<here>>> " + text[pos : pos + 40]
    return " ".join(window.split())


def extract_json(text: str, top_keys: Iterable[str] = ()) -> Any:
    """Parse the first JSON object or array in a model answer.

    A value that starts like an answer (it has a key) but breaks further on is repaired,
    and if that fails the syntax error is reported with its position. It is never
    skipped: skipping it would return an object from inside it, and the error that
    follows would blame the wrong thing.
    """
    answer, _ = split_reasoning(text)
    candidates = [m.group(1) for m in _FENCE.finditer(answer)] + [answer]
    decoder = json.JSONDecoder()
    broken: tuple[str, json.JSONDecodeError] | None = None
    for candidate in candidates:
        for i, ch in enumerate(candidate):
            if ch not in "{[":
                continue
            try:
                value, _ = decoder.raw_decode(candidate, i)
                return value
            except json.JSONDecodeError as exc:
                if not _KEY.search(candidate, i, exc.pos):
                    continue  # a brace in prose, not the answer: scan on
                try:
                    value, _ = decoder.raw_decode(repair_json(candidate[i:], top_keys))
                    return value
                except json.JSONDecodeError:
                    broken = broken or (candidate, exc)
                    break  # the answer is broken: no object from inside it
    if broken:
        candidate, exc = broken
        raise JSONExtractionError(
            f"invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}, near: "
            + _near(candidate, exc.pos)
        )
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
    check: Callable[[T], str | None] | None = None,
    **kwargs: Any,
) -> tuple[T, list[LLMResult]]:
    """Call the model and return a validated instance of `schema` plus all raw results.

    `check` looks at an answer that validated and returns a message when it still cannot
    be used (an answer that copies the prompt's own example); the message goes back to
    the model like a validation error.
    """
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
        cause: Exception | None = None
        try:
            out = schema.model_validate(extract_json(result.text, schema.model_fields))
        except (JSONExtractionError, ValidationError) as exc:
            cause = exc
            error: str | None = str(exc)[:_MAX_ERROR_CHARS]
        else:
            error = check(out) if check else None
            if error is None:
                return out, results
        if attempt == max_repairs:
            raise LLMOutputError(
                f"model output did not validate as {schema.__name__}: {error}", results
            ) from cause
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
