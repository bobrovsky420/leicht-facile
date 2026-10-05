"""Separate a thinking model's reasoning from its visible answer.

Depending on the serving stack, reasoning arrives either in a separate field of the
response (`reasoning_content` or `reasoning`) or inline in the text, wrapped in
Apertus' `<|inner_prefix|>` ... `<|inner_suffix|>` tokens. Some stacks use
`<think>` ... `</think>` instead. Both inline forms are handled here.
"""

from __future__ import annotations

import re

_MARKERS = [
    ("<|inner_prefix|>", "<|inner_suffix|>"),
    ("<think>", "</think>"),
]


def split_reasoning(text: str) -> tuple[str, str | None]:
    """Return (answer, reasoning). Reasoning is None when the text contains none.

    An opening marker without a closing one means the output was cut off while the
    model was still reasoning: everything after the marker is reasoning and the
    answer is empty.
    """
    reasoning_parts: list[str] = []
    answer = text
    for start, end in _MARKERS:
        pattern = re.compile(re.escape(start) + r"(.*?)" + re.escape(end), re.DOTALL)
        reasoning_parts.extend(m.strip() for m in pattern.findall(answer))
        answer = pattern.sub("", answer)
        if start in answer:
            head, _, tail = answer.partition(start)
            reasoning_parts.append(tail.strip())
            answer = head
        # A stray closing marker: some templates put the opening one in the prompt.
        if end in answer:
            head, _, tail = answer.partition(end)
            reasoning_parts.append(head.strip())
            answer = tail
    reasoning = "\n\n".join(p for p in reasoning_parts if p) or None
    return answer.strip(), reasoning
