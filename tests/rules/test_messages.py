"""The checker's messages (rules/messages.py): every hit names a template with exactly
its placeholders, every template is used, and a Finding carries key and values."""

from __future__ import annotations

import ast
import string
from collections.abc import Iterator
from pathlib import Path

import leichtfacile.rules as rules_package
from leichtfacile.rules import RULES, get_checker
from leichtfacile.rules.messages import MESSAGES, hit, recover
from leichtfacile.rules.values import HARD_KINDS
from leichtfacile.schemas import Block, Draft

RULES_DIR = Path(rules_package.__file__).parent
MODULES = ("de.py", "fr.py", "document.py", "layout.py")
# Keyword arguments of hit() that are fields of the Hit, not placeholders.
HIT_FIELDS = {"evidence", "suggestion", "severity", "fact_id", "segment_ids", "block_id"}


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _keys(node: ast.expr) -> list[str]:
    """The message keys a hit() call may use: a literal, either branch of a
    conditional, or the literal prefix of an f-string (FACT-06.<kind>) with a *."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _keys(node.body) + _keys(node.orelse)
    if isinstance(node, ast.JoinedStr) and isinstance(node.values[0], ast.Constant):
        return [node.values[0].value + "*"]
    raise AssertionError(f"hit() needs a literal key, got {ast.dump(node)}")


def _templates(key: str, params: set[str]) -> list[str]:
    """The templates a key stands for: every key behind a * prefix, else the key, each
    as its .one/.other pair when the call passes a count n."""
    keys = [k for k in MESSAGES if k.startswith(key[:-1])] if key.endswith("*") else [key]
    assert keys, key
    if "n" in params:
        return [f"{k}.{form}" for k in keys for form in ("one", "other")]
    return keys


def _calls() -> Iterator[tuple[str, list[str], set[str]]]:
    """(module, keys, placeholder names) for every hit(...) call in the rule modules."""
    for name in MODULES:
        tree = ast.parse((RULES_DIR / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "hit":
                continue
            assert len(node.args) == 1, f"{name}: hit() takes the key and keywords"
            names = {k.arg for k in node.keywords}
            assert None not in names, f"{name}: no **kwargs in hit()"
            yield name, _keys(node.args[0]), names - HIT_FIELDS


def test_every_hit_names_a_template_with_exactly_its_placeholders() -> None:
    calls = list(_calls())
    assert len(calls) > 90
    for module, keys, params in calls:
        for key in keys:
            for template in _templates(key, params):
                assert template in MESSAGES, f"{module}: {template}"
                assert _fields(MESSAGES[template]) == params, f"{module}: {template}"


def test_every_template_is_used_and_belongs_to_a_rule() -> None:
    used: set[str] = set()
    for _, keys, params in _calls():
        for key in keys:
            used |= set(_templates(key, params))
    assert set(MESSAGES) == used
    for key in MESSAGES:
        assert key.split(".")[0] in RULES, key
    assert {f"FACT-06.{kind}" for kind in HARD_KINDS} <= set(MESSAGES)


def test_templates_use_plain_hyphens() -> None:
    for key, text in MESSAGES.items():
        assert chr(0x2013) not in text and chr(0x2014) not in text, key


def test_hit_formats_the_english_text_and_keeps_key_and_values() -> None:
    h = hit("LEN-01", words=23, limit=12, level="A2", evidence="x", severity="warn")
    assert h.message == "The sentence has 23 words; the limit for A2 is 12."
    assert (h.key, h.params) == ("LEN-01", {"words": 23, "limit": 12, "level": "A2"})
    assert (h.evidence, h.severity) == ("x", "warn")
    one, none = hit("LAY-03.few", n=1, blocks=12), hit("LAY-03.few", n=0, blocks=12)
    assert one.message.startswith("1 heading for 12 blocks")
    assert none.message.startswith("0 headings for 12 blocks")
    assert one.key == none.key == "LAY-03.few"


def test_findings_carry_key_and_values() -> None:
    draft = Draft(
        doc_id="d",
        lang="de",
        level="A2",
        blocks=[
            Block(
                id="b001",
                kind="sentence",
                text="Sie bekommen Geld, weil Sie wenig verdienen, wenn Sie das Formular schicken.",
            )
        ],
    )
    findings = get_checker("de").check(draft).findings
    by_rule = {f.rule_id: f for f in findings}
    f = by_rule["LEN-02"]
    assert f.message_key == "LEN-02.sub"
    assert f.message_params == {"opener": "weil", "clauses": 3, "limit": 1, "level": "A2"}
    assert f.message == MESSAGES["LEN-02.sub"].format(**f.message_params)
    assert all(f.message_key is not None for f in findings)


def test_recover_reads_key_and_values_off_an_old_english_message() -> None:
    old = (
        "Subordinate clause ('die'): 3 clauses in one sentence. "
        "At most 1 for A2: one statement per sentence."
    )
    values = {"opener": "die", "clauses": "3", "limit": "1", "level": "A2"}
    assert recover("LEN-02", old) == ("LEN-02.sub", values)
    assert recover("LEN-02-FR", old) == ("LEN-02-FR.sub", values)  # the rule picks the key
    few = "1 heading for 12 blocks: add headings, ideally as the reader's questions."
    assert recover("LAY-03", few) == ("LAY-03.few", {"n": 1, "blocks": "12"})
    assert recover("LEN-01", "Some text an older checker wrote.") is None
    assert recover("LEN-01", old) is None


def test_every_template_round_trips_through_recover() -> None:
    for key, template in MESSAGES.items():
        names = sorted(_fields(template))
        values: dict[str, str | int] = {name: f"v{i}" for i, name in enumerate(names)}
        expected_key = key
        if key.endswith((".one", ".other")):
            expected_key, form = key.rsplit(".", 1)
            values["n"] = 1 if form == "one" else 2
        recovered = recover(key.split(".")[0], template.format(**values))
        assert recovered == (expected_key, values), key
