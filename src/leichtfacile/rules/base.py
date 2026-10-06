"""Rule registry, level thresholds and the context every check receives.

Each rule of docs/rules.md is registered here once, with its id, severity per level,
scope and the instruction for the writer prompt. The checker runs the registered
check functions, and the style guide in the writer prompt is generated from the same
registry, so prompt and checker cannot drift apart. A test keeps the registry and
docs/rules.md in sync.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

from leichtfacile.schemas import Level, Severity

if TYPE_CHECKING:
    from spacy.tokens import Span

Scope = Literal["sentence", "block", "document", "factsheet", "export", "judge"]


@dataclass(frozen=True)
class LevelParams:
    """Thresholds per level (docs/rules.md, "Thresholds per level")."""

    level: Level
    max_words: int  # LEN-01
    optimum_words: int | None
    max_clauses: int  # LEN-02
    max_word_letters: int  # LEX-01 (German)
    max_line_chars: int  # LAY-02
    readability_target: float  # READ-01 (German, Amstad)
    max_heading_words: int = 8  # LAY-03


PARAMS: dict[str, LevelParams] = {
    "A2": LevelParams("A2", 12, 8, 1, 13, 85, 70.0),
    "B1": LevelParams("B1", 15, None, 2, 16, 85, 60.0),
}
# French needs about a quarter more words than German for the same content (articles,
# prepositions): on the official easy-language pages the mean sentence has 7.3 words in
# French and 5.9 in German (calibration, docs/rules.md). The French limits scale with it.
LANG_PARAMS: dict[str, dict[str, LevelParams]] = {
    "fr": {
        "A2": replace(PARAMS["A2"], max_words=15, optimum_words=10),
        "B1": replace(PARAMS["B1"], max_words=18),
    },
}


def params_for(lang: str | None, level: str) -> LevelParams:
    """The thresholds for a language and level; PARAMS unless the language has its own."""
    return LANG_PARAMS.get(lang or "", {}).get(level) or PARAMS[level]


@dataclass(frozen=True)
class Hit:
    """One occurrence found by a check, built by `messages.hit()`; the checker turns it
    into a Finding."""

    message: str  # English, from the template `key` in messages.py
    evidence: str = ""
    suggestion: str | None = None
    severity: Severity | None = None  # overrides the rule's severity for this level
    fact_id: str | None = None
    segment_ids: tuple[str, ...] = ()
    block_id: str | None = None  # document-scope checks name the block, if any
    key: str | None = None  # the message template; the UI translates by it
    params: dict[str, str | int | float] = field(default_factory=dict)  # its placeholders


@dataclass
class BlockInfo:
    id: str
    kind: str  # heading | sentence | list_item
    text: str
    sentences: list[Span] = field(default_factory=list)


@dataclass
class Context:
    """What a check may look at besides the sentence or block itself."""

    lang: str
    params: LevelParams
    glossary: set[str] = field(default_factory=set)  # lowercased terms, without Mediopunkt
    blocks: list[BlockInfo] = field(default_factory=list)
    block_index: int = 0  # index of the block being checked
    addresses_reader: bool = False  # the text says Sie / Ihnen / Ihr to the reader
    introduced: set[str] = field(default_factory=set)  # abbreviations explained in the text

    @property
    def level(self) -> Level:
        return self.params.level

    def previous_block(self) -> BlockInfo | None:
        return self.blocks[self.block_index - 1] if self.block_index > 0 else None

    def in_glossary(self, word: str) -> bool:
        return _glossary_key(word) in self.glossary


def _glossary_key(word: str) -> str:
    return word.replace("\u00b7", "").replace("-", "").strip().lower()


def glossary_keys(terms: Iterable[str]) -> set[str]:
    keys: set[str] = set()
    for term in terms:
        keys.add(_glossary_key(term))
        for part in term.split():  # "die Prämien·verbilligung" also covers the noun alone
            if len(part) > 3:
                keys.add(_glossary_key(part))
    return keys


CheckFn = Callable[..., Iterable[Hit]]


@dataclass(frozen=True)
class RuleSpec:
    id: str
    lang: str | None  # None: applies to every language
    title: str  # the "Rule" column of docs/rules.md
    severity: dict[str, Severity]  # per level
    scope: Scope
    # Instruction for the writer prompt in the rule's language, one text for all levels
    # or one per level; {max_words} and the other LevelParams fields are filled in.
    guide: str | dict[str, str] | None = None
    guide_levels: tuple[str, ...] = ("A2", "B1")
    kinds: tuple[str, ...] = ("sentence", "list_item", "heading")  # block kinds checked
    check: CheckFn | None = None

    def severity_for(self, level: str) -> Severity:
        return self.severity[level]

    def guide_for(self, level: str) -> str | None:
        if level not in self.guide_levels or self.guide is None:
            return None
        text = self.guide.get(level) if isinstance(self.guide, dict) else self.guide
        if text is None:
            return None
        return text.format(**params_for(self.lang, level).__dict__)


RULES: dict[str, RuleSpec] = {}


def sev(a2: Severity, b1: Severity | None = None) -> dict[str, Severity]:
    return {"A2": a2, "B1": b1 or a2}


def rule(
    rule_id: str,
    *,
    lang: str | None,
    title: str,
    severity: dict[str, Severity],
    scope: Scope,
    guide: str | dict[str, str] | None = None,
    guide_levels: tuple[str, ...] = ("A2", "B1"),
    kinds: tuple[str, ...] = ("sentence", "list_item", "heading"),
) -> Callable[[CheckFn], CheckFn]:
    """Register a check function under a rule id."""

    def decorator(fn: CheckFn) -> CheckFn:
        if rule_id in RULES:
            raise ValueError(f"rule {rule_id} registered twice")
        RULES[rule_id] = RuleSpec(
            rule_id, lang, title, severity, scope, guide, guide_levels, kinds, fn
        )
        return fn

    return decorator


def declare(
    rule_id: str,
    *,
    lang: str | None,
    title: str,
    severity: dict[str, Severity],
    scope: Scope,
    guide: str | dict[str, str] | None = None,
    guide_levels: tuple[str, ...] = ("A2", "B1"),
) -> None:
    """Register a rule without a check function (judge rules, metric-only rules)."""
    if rule_id in RULES:
        raise ValueError(f"rule {rule_id} registered twice")
    RULES[rule_id] = RuleSpec(rule_id, lang, title, severity, scope, guide, guide_levels)


def rules_for(lang: str, scope: Scope) -> Iterator[RuleSpec]:
    for spec in RULES.values():
        if spec.scope == scope and spec.check and spec.lang in (None, lang):
            yield spec
