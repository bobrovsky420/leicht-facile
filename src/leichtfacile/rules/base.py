"""Rule registry, level thresholds and the context every check receives.

Each rule of docs/rules.md is registered here once, with its id, severity per level,
scope and the instruction for the writer prompt. A rule of the language families is
declared in `catalog.py` and gets its checks from the language modules (`de.py`,
`fr.py`) or from `shared.py`, which holds the checks both languages share; a rule that
applies to every language (facts, layout, readability) declares itself with its check.
The checker runs the check a rule has for the document's language, and the style guide
in the writer prompt is generated from the same registry, so prompt and checker cannot
drift apart. A test keeps the registry and docs/rules.md in sync.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

from leichtfacile.schemas import LANGS, Level, Severity, base_lang

if TYPE_CHECKING:
    from spacy.tokens import Span

Scope = Literal["sentence", "block", "document", "factsheet", "export", "judge"]
EVERY_LANGUAGE = "*"  # the key of a check that serves every language


@dataclass(frozen=True)
class LevelParams:
    """Thresholds per level (docs/rules.md, "Thresholds per level")."""

    level: Level
    max_words: int  # LEN-01
    max_clauses: int  # LEN-02
    max_word_letters: int  # LEX-01 (German)
    max_line_chars: int  # LAY-02
    readability_target: float  # READ-01 (German, Amstad)
    max_heading_words: int = 8  # LAY-03


PARAMS: dict[str, LevelParams] = {
    "A2": LevelParams("A2", 12, 1, 13, 85, 70.0),
    "B1": LevelParams("B1", 15, 2, 16, 85, 60.0),
}
# French needs about a quarter more words than German for the same content (articles,
# prepositions): on the official easy-language pages the mean sentence has 7.3 words in
# French and 5.9 in German (calibration, docs/rules.md). The French limits scale with it.
LANG_PARAMS: dict[str, dict[str, LevelParams]] = {
    "fr": {
        "A2": replace(PARAMS["A2"], max_words=15),
        "B1": replace(PARAMS["B1"], max_words=18),
    },
    # Italian needs about half more words than German: on the 14 official Italian
    # easy-language pages the mean sentence has 8.9 words and 95 percent of the
    # sentences have at most 19 (calibration of 28 October 2026, docs/rules.md).
    "it": {
        "A2": replace(PARAMS["A2"], max_words=18),
        "B1": replace(PARAMS["B1"], max_words=21),
    },
}


def params_for(lang: str | None, level: str) -> LevelParams:
    """The thresholds for a language and level; PARAMS unless the language has its own.
    A variety key (`de-AT`) takes its language's: the limits are the language's."""
    return LANG_PARAMS.get(base_lang(lang or ""), {}).get(level) or PARAMS[level]


@dataclass(frozen=True)
class Hit:
    """One occurrence found by a check, built by `messages.hit()`; the checker turns it
    into a Finding."""

    key: str  # the message template in messages.py
    params: dict[str, str | int | float] = field(default_factory=dict)  # its placeholders
    evidence: str = ""
    suggestion: str | None = None
    severity: Severity | None = None  # overrides the rule's severity for this level
    fact_id: str | None = None
    segment_ids: tuple[str, ...] = ()
    block_id: str | None = None  # document-scope checks name the block, if any


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
    # The national variety the text is checked in (schemas.variety: `de`, `de-DE`, ...);
    # the language's key when the checker is made for a language alone.
    variety: str = ""
    glossary: set[str] = field(default_factory=set)  # lowercased terms, without Mediopunkt
    blocks: list[BlockInfo] = field(default_factory=list)
    block_index: int = 0  # index of the block being checked
    addresses_reader: bool = False  # Sie or du, vous or tu, Lei or voi in the text
    introduced: set[str] = field(default_factory=set)  # abbreviations explained in the text
    # Decision mode, export checks: the authority's fixed text, which the export must
    # begin and end with (FACT-07) and which the layout rules leave alone.
    notice: str | None = None

    def __post_init__(self) -> None:
        self.variety = self.variety or self.lang

    @property
    def level(self) -> Level:
        return self.params.level

    @property
    def region(self) -> str:
        """The region of the variety: CH, DE or AT; CH for a plain language code."""
        return self.variety.partition("-")[2] or "CH"

    def previous_block(self) -> BlockInfo | None:
        return self.blocks[self.block_index - 1] if self.block_index > 0 else None

    def in_glossary(self, word: str) -> bool:
        return _glossary_key(word) in self.glossary


def _glossary_key(word: str) -> str:
    return word.replace("·", "").replace("-", "").strip().lower()


def glossary_keys(terms: Iterable[str]) -> set[str]:
    keys: set[str] = set()
    for term in terms:
        keys.add(_glossary_key(term))
        for part in term.split():  # "die Prämien·verbilligung" also covers the noun alone
            if len(part) > 3:
                keys.add(_glossary_key(part))
    return keys


CheckFn = Callable[..., Iterable[Hit]]
Guide = str | dict[str, str]  # one instruction for every level, or one per level


@dataclass
class RuleSpec:
    id: str
    title: str  # the "Rule" column of docs/rules.md, in English
    severity: dict[str, Severity]  # per level
    scope: Scope
    kinds: tuple[str, ...] = ("sentence", "list_item", "heading")  # block kinds checked
    # The checks by language or variety key (`de`, `de-AT`), or one under
    # EVERY_LANGUAGE; a rule the judge decides or a metric reports has none. A variety
    # without a check of its own takes its language's.
    checks: dict[str, CheckFn] = field(default_factory=dict)
    # The instruction for the writer prompt, by language or variety key; {max_words} and
    # the other LevelParams fields are filled in.
    guides: dict[str, Guide] = field(default_factory=dict)

    @property
    def langs(self) -> tuple[str, ...]:
        """The languages with a check of their own; empty for a check that serves every
        language, and for a rule without a check."""
        return tuple(lang for lang in self.checks if lang != EVERY_LANGUAGE)

    def check_for(self, lang: str) -> CheckFn | None:
        """The check for a language or a variety key, the variety's own first."""
        return (
            self.checks.get(lang)
            or self.checks.get(base_lang(lang))
            or self.checks.get(EVERY_LANGUAGE)
        )

    def severity_for(self, level: str) -> Severity:
        return self.severity[level]

    def guide_for(self, lang: str, level: str) -> str | None:
        guide = self.guides.get(lang)
        if guide is None:
            guide = self.guides.get(base_lang(lang))
        text = guide.get(level) if isinstance(guide, dict) else guide
        if text is None:
            return None
        return text.format(**params_for(lang, level).__dict__)


RULES: dict[str, RuleSpec] = {}


def sev(a2: Severity, b1: Severity | None = None) -> dict[str, Severity]:
    return {"A2": a2, "B1": b1 or a2}


def declare(
    rule_id: str,
    *,
    title: str,
    severity: dict[str, Severity],
    scope: Scope,
    kinds: tuple[str, ...] = ("sentence", "list_item", "heading"),
) -> RuleSpec:
    """Register a rule: the language rules in catalog.py, the judge's and the metrics'
    rules where they are listed. The checks attach with `rule`."""
    if rule_id in RULES:
        raise ValueError(f"rule {rule_id} declared twice")
    RULES[rule_id] = RuleSpec(rule_id, title, severity, scope, kinds)
    return RULES[rule_id]


def rule(
    rule_id: str,
    *,
    lang: str | tuple[str, ...] | None,
    title: str | None = None,
    severity: dict[str, Severity] | None = None,
    scope: Scope | None = None,
    guide: Guide | dict[str, Guide] | None = None,
    kinds: tuple[str, ...] | None = None,
) -> Callable[[CheckFn], CheckFn]:
    """Attach a check function to a rule for one language, for several (`lang` a
    tuple, with the guide by language) or for every language (None). A rule not
    declared yet is declared here with `title`, `severity` and `scope`; a declared one
    takes no second declaration."""
    langs = (lang,) if isinstance(lang, str) or lang is None else tuple(lang)

    def decorator(fn: CheckFn) -> CheckFn:
        spec = RULES.get(rule_id)
        if spec is None:
            if title is None or severity is None or scope is None:
                raise ValueError(f"rule {rule_id} is not declared (rules/catalog.py)")
            spec = declare(
                rule_id,
                title=title,
                severity=severity,
                scope=scope,
                kinds=kinds or ("sentence", "list_item", "heading"),
            )
        elif title is not None or severity is not None or scope is not None or kinds:
            raise ValueError(f"rule {rule_id} is declared already: attach the check alone")
        for code in langs:
            key = code or EVERY_LANGUAGE
            if key in spec.checks:
                raise ValueError(f"rule {rule_id}: a check for {key} is registered twice")
            spec.checks[key] = fn
            if guide is not None and code is not None:
                spec.guides[code] = guide[code] if len(langs) > 1 else guide  # type: ignore[index,assignment]
        return fn

    return decorator


def rules_for(lang: str, scope: Scope) -> Iterator[tuple[RuleSpec, CheckFn]]:
    """The rules of a scope with the check they have for the language or variety key."""
    for spec in RULES.values():
        if spec.scope != scope:
            continue
        check = spec.check_for(lang)
        if check is not None:
            yield spec, check


def checked_languages() -> tuple[str, ...]:
    """The languages with checks of their own, in the order of LANGS: the ones the Check
    page offers and the README counts. Call it after the rules are registered
    (importing `leichtfacile.rules` does that)."""
    return tuple(lang for lang in LANGS if any(lang in spec.checks for spec in RULES.values()))
