"""The checker's messages (rules/messages.py): every hit names a template with exactly
its placeholders, every template is used, and a Finding carries key and values."""

from __future__ import annotations

import ast
import string
from collections.abc import Iterator
from pathlib import Path

import pytest

import leichtfacile.rules as rules_package
from leichtfacile.rules import RULES, get_checker
from leichtfacile.rules.messages import (
    MESSAGES,
    hit,
    plural_form,
    render,
    render_finding,
    variant,
)
from leichtfacile.rules.values import HARD_KINDS
from leichtfacile.schemas import Block, Draft

RULES_DIR = Path(rules_package.__file__).parent
MODULES = (
    "de.py", "fr.py", "shared.py", "document.py", "decision.py", "medication.py", "layout.py",
)  # fmt: skip
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
    assert set(MESSAGES) == used | {"legacy"}  # legacy: findings stored before the keys
    for key in MESSAGES:
        assert key == "legacy" or key.split(".")[0] in RULES, key
    assert {f"FACT-06.{kind}" for kind in HARD_KINDS} <= set(MESSAGES)


def test_templates_use_plain_hyphens() -> None:
    for key, text in MESSAGES.items():
        assert chr(0x2013) not in text and chr(0x2014) not in text, key


def test_hit_keeps_key_and_values_and_render_gives_the_english_text() -> None:
    h = hit("LEN-01", words=23, limit=12, level="A2", evidence="x", severity="warn")
    assert (h.key, h.params) == ("LEN-01", {"words": 23, "limit": 12, "level": "A2"})
    assert render(h.key, h.params) == "The sentence has 23 words; the limit for A2 is 12."
    assert (h.evidence, h.severity) == ("x", "warn")
    one, none = hit("LAY-03.few", n=1, blocks=12), hit("LAY-03.few", n=0, blocks=12)
    assert render(one.key, one.params).startswith("1 heading for 12 blocks")
    assert render(none.key, none.params).startswith("0 headings for 12 blocks")
    assert one.key == none.key == "LAY-03.few"
    assert render("legacy", {"text": "an older checker's text"}) == "an older checker's text"
    with pytest.raises(KeyError):
        hit("LEN-99", words=1)  # no such template: a slip in a check


def test_plural_forms_follow_the_language() -> None:
    assert [plural_form("en", n) for n in (0, 1, 2)] == ["other", "one", "other"]
    assert [plural_form("de", n) for n in (0, 1, 2)] == ["other", "one", "other"]
    assert [plural_form("fr", n) for n in (0, 1, 2)] == ["one", "one", "other"]
    assert plural_form("fr", "1") == "one" and plural_form("xx", "x") == "other"


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
    assert f.key == "LEN-02.sub"
    assert f.params == {"opener": "weil", "clauses": 3, "limit": 1, "level": "A2"}
    assert render_finding(f) == MESSAGES["LEN-02.sub"].format(**f.params)
    assert all(f.key in MESSAGES or variant(f.key, f.params) in MESSAGES for f in findings)


@pytest.mark.parametrize(
    ("lang", "text", "key"),
    [
        ("de", "Der Antragsteller wartet.", "LEX-06.no_address"),
        ("de", "Der Antragsteller wartet. Wir schicken Ihnen Post.", "LEX-06"),
        ("de", "Der Antragsteller wartet. Wir schicken dir Post.", "LEX-06"),
        ("de", "Der Antragsteller wartet. Du bekommst Post.", "LEX-06"),
        ("fr", "Le requérant attend.", "LEX-06.no_address"),
        ("fr", "Le requérant attend. Nous vous écrivons.", "LEX-06"),
        ("fr", "Le requérant attend. Tu reçois une lettre.", "LEX-06"),
        ("fr", "Le requérant attend. Nous t'écrivons.", "LEX-06"),
    ],
)
def test_lex_06_reminder_only_where_the_text_never_addresses_the_reader(
    lang: str, text: str, key: str
) -> None:
    """The informal form (du, tu) addresses the reader too: a text in it gets the short
    LEX-06 finding, not the reminder that easy language talks to the reader directly."""
    draft = Draft(
        doc_id="d", lang=lang, level="A2", blocks=[Block(id="b001", kind="sentence", text=text)]
    )
    (finding,) = [f for f in get_checker(lang).check(draft).findings if f.rule_id == "LEX-06"]
    assert finding.key == key
