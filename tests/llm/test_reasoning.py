from __future__ import annotations

import pytest

from leichtfacile.llm.reasoning import split_reasoning


@pytest.mark.parametrize(
    ("text", "answer", "reasoning"),
    [
        ("Nur Antwort.", "Nur Antwort.", None),
        ("<|inner_prefix|>Denken<|inner_suffix|>Antwort", "Antwort", "Denken"),
        ("<think>\nDenken\n</think>\n\nAntwort", "Antwort", "Denken"),
        ("<|inner_prefix|>Abgeschnitten", "", "Abgeschnitten"),
        ("Denken ohne Anfang<|inner_suffix|>Antwort", "Antwort", "Denken ohne Anfang"),
        (
            "<|inner_prefix|>A<|inner_suffix|>X<|inner_prefix|>B<|inner_suffix|>Y",
            "XY",
            "A\n\nB",
        ),
    ],
)
def test_split_reasoning(text, answer, reasoning):
    assert split_reasoning(text) == (answer, reasoning)


def test_control_tokens_are_removed_from_the_answer():
    text = "<|inner_prefix|>17 + 25 = 42<|inner_suffix|>42<|assistant_end|>"
    answer, reasoning = split_reasoning(text)
    assert answer == "42"
    assert reasoning == "17 + 25 = 42"
