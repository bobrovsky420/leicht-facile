"""Layout rules checked on the exported text (docs/rules.md, LAY-01 and LAY-02)."""

from __future__ import annotations

import re
from collections.abc import Iterator

from leichtfacile.rules.base import PARAMS, Context, Hit, rule, sev
from leichtfacile.rules.messages import hit

# A sentence ends at . ! ? followed by a space and a capital letter or a digit. Dots in
# dates (4. Februar), times (9.00) and amounts (1'500.-) do not end a sentence.
_SENTENCE_END_RE = re.compile(r"(?<![\d\s])[.!?](?=\s+[A-ZÄÖÜ\"])")


@rule(
    "LAY-01",
    lang=None,
    title="One sentence per line",
    severity=sev("warn"),
    scope="export",
)
def lay_01(lines: list[str], ctx: Context) -> Iterator[Hit]:
    for n, line in enumerate(lines, 1):
        if _SENTENCE_END_RE.search(line.strip()):
            yield hit("LAY-01", line=n, evidence=line.strip())


@rule(
    "LAY-02",
    lang=None,
    title="Lines of at most 85 characters",
    severity=sev("warn"),
    scope="export",
)
def lay_02(lines: list[str], ctx: Context) -> Iterator[Hit]:
    limit = ctx.params.max_line_chars
    for n, line in enumerate(lines, 1):
        if len(line) > limit:
            yield hit("LAY-02", line=n, chars=len(line), limit=limit, evidence=line)


def wrap_sentence(sentence: str, width: int = PARAMS["A2"].max_line_chars) -> list[str]:
    """Break a long sentence into lines of at most `width` characters, preferably
    after a comma or before und / oder / aber, otherwise between words."""
    sentence = sentence.strip()
    if len(sentence) <= width:
        return [sentence]
    words = sentence.split(" ")
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > width:
            # Prefer to break at the last clause boundary within the line.
            cut = _clause_break(current)
            if cut:
                lines.append(" ".join(current[:cut]))
                current = current[cut:]
            else:
                lines.append(" ".join(current))
                current = []
        current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _clause_break(words: list[str]) -> int | None:
    for i in range(len(words) - 1, max(0, len(words) // 2) - 1, -1):
        if words[i].endswith(",") and i + 1 < len(words):
            return i + 1
        if words[i].lower() in ("und", "oder", "aber", "et", "ou", "mais", "e", "o", "ma") and i:
            return i
    return None
