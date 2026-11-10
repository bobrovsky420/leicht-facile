"""The checks on a model's answer that need no model (docs/architecture.md §4.2, §4.3
and §4.6), as predicates over the answer's texts: whether it copies the prompt's own
examples (`copy_check`), brings their topics or their values into a document that has
none (`topic_check`, `drop_topical`), or holds values that neither the source nor the
fact sheet has (`foreign_check`). A stage gives them to `complete_json`, which sends an
answer back once with the check's message; what the second answer still has of the
examples, the stage leaves out (`drop_topical`).
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from leichtfacile.pipeline.labels import label
from leichtfacile.pipeline.models import RepairOut, UnderstandOut, WriteOut
from leichtfacile.pipeline.prompts import examples, level_name, mode_context, render
from leichtfacile.pipeline.versions import stems
from leichtfacile.rules.document import KnownValues
from leichtfacile.rules.styleguide import style_guide
from leichtfacile.rules.values import HARD_KINDS, Value, extract_values, matches
from leichtfacile.schemas import variety_chain
from leichtfacile.varieties import variety as variety_table

log = logging.getLogger(__name__)

# -- the prompt's own examples ---------------------------------------------------------

# Rendering a template without its document gives the static text: the instructions,
# the JSON example and (for write) the few-shot pairs.
_STATIC_CONTEXT: dict[str, dict[str, str]] = {
    "understand": {"source": ""},
    "write": {"level": "A2", "style_guide": "", "section": "", "factsheet": "", "source": ""},
    "repair": {
        "level": "A2", "style_guide": "", "flagged": "", "missing": "", "factsheet": "",
        "draft": "", "source": "",
    },
}  # fmt: skip
_QUOTED = re.compile(r'"([^"\n]{12,})"')
COPY_LIMIT = 2  # sentences from the examples that make an answer a copy
# Words of the examples' topics (a resident parking permit, a dog tax). A sentence with
# one of them, in a document that has none, is example content even in paraphrase: on
# CSCS the 8B wrote "Sie melden neue Hunde bei der Einwohnerkontrolle an" into a page
# about EL costs, with only 2 of 12 sentences verbatim (6 October 2026). Matched on
# lowercased text without the Mediopunkt; "hundert" is not a dog.
EXAMPLE_TOPIC_WORDS: dict[str, tuple[str, ...]] = {
    "de-CH": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhundesteuer",
        r"\b(?:anwohner)?parkkarte",
        r"\bimpfausweis",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
        # The office of the examples: the repair example's addition "Rufen Sie die
        # Einwohner·kontrolle an" came back with a number of the document in 4 P2 jobs of
        # the CSCS evaluation and 3 example builds (by 8 October 2026), in documents that
        # never name the office.
        r"\beinwohnerkontrolle",
        r"\bchip\b",  # "die Nummer vom Chip" of the write example
    ),
    # Germany and Austria (29 October 2026): the shared JSON example's dog tax, and the
    # examples of their own (prompts/de-DE/examples, de-AT/examples): a parking permit
    # and a dog-tax letter; the office comes from the variety's table (`_topic_patterns`).
    "de-DE": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhundesteuer",
        r"\b(?:bewohner)?parkausweis",
        r"\bimpfausweis",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
        r"\bchip\b",
    ),
    "de-AT": (
        r"\bhund(?:e|es|en|s)?\b",
        r"\bhunde(?:steuer|abgabe)",
        r"\bparkpickerl",
        r"\bimpf(?:ausweis|pass)",
        r"\bfrontscheibe",
        r"\bwindschutzscheibe",
        r"\bchip\b",
    ),
    "fr-CH": (
        r"\bchiens?\b",
        r"\bcarte de stationnement",
        r"\bpare-brise",
        r"\bcarnet de vaccination",
        r"\bcontrôle des habitants",
        # The dog's microchip of the write example: "le numéro de la puce" stood in five
        # sentences of a final draft about petitions in the run of 11 October 2026.
        r"\bpuce\b",
    ),
    # The Italian examples (28 October 2026) are the French ones in Italian wording:
    # the dog and its tax, the parking permit, the office and the microchip of the
    # write example. Not measured on a model yet.
    "it-CH": (
        r"\bcan[ei]\b",
        r"\btassa sui cani",
        r"\b(?:carta|contrassegno) di parcheggio",
        r"\bparabrezza",
        r"\blibretto delle vaccinazioni",
        r"\bcontrollo (?:degli )?abitanti",
        r"\bmicrochip\b",
    ),
}


def example_key(text: str) -> str:
    # Without the compound marks: the Mediopunkt, and the hyphen between letters that
    # Germany and Austria write for it (Hunde-Steuer).
    plain = re.sub(r"(?<=[^\W\d_])-(?=[^\W\d_])", "", text.lower().replace("·", ""))
    return " ".join(plain.split()).rstrip(".!?:")


def _static_renders(lang: str, stage: str) -> list[str]:
    """The prompt without its document, once per level where the level matters: the
    instructions, the JSON example, the style guide (write and repair) and the few-shot
    pairs (write). The style guide is in since 8 October 2026: a decision-mode draft on
    the 8B carried the write prompt's style guide as a section of the draft."""
    levels = ("A2", "B1") if "style_guide" in _STATIC_CONTEXT[stage] else ("A2",)
    renders = []
    for level in levels:
        context = dict(_STATIC_CONTEXT[stage], level=level, level_name=level_name(lang, level))
        if "style_guide" in context:
            context["style_guide"] = style_guide(lang, level)
        context.update(mode_context(stage))
        if stage == "write":
            context["examples"] = examples(lang)
        renders.append(render(lang, stage, **context))
    return renders


@lru_cache(maxsize=16)
def example_keys(lang: str, stage: str) -> frozenset[str]:
    """The sentences of a prompt's own examples and style guide, normalised, to
    recognise an answer that copies them. On the Public AI 8B, 4 of 12 dev drafts were
    the write prompt's JSON example, word for word (6 October 2026). A list marker in
    front of a line (the style guide's `- `) is not part of the key."""
    keys: set[str] = set()
    for text in _static_renders(lang, stage):
        keys |= {example_key(line.lstrip(" -*")) for line in text.splitlines()}
        keys |= {example_key(q) for q in _QUOTED.findall(text)}
    return frozenset(k for k in keys if len(k) >= 12)


def copied_sentences(texts: list[str], lang: str, stage: str) -> int:
    return len(_copied(texts, lang, stage))


def _copied(texts: list[str], lang: str, stage: str) -> list[str]:
    keys = example_keys(lang, stage)
    return [t for t in texts if example_key(t) in keys]


_SPECIFIC_STEMS = 3  # content words that make a sentence more than a stock phrase


def _specific(text: str, lang: str) -> bool:
    """Whether a sentence says something of its own: a hard value, or three content
    words or more (`versions.stems`). "Haben Sie Fragen?" and "Sie können von Montag bis Freitag
    anrufen." are stock phrases of easy language that the few-shot example shares with
    honest drafts: two of them in a draft of three sentences were a copied example, sent
    back, and a second such answer failed the stage (audit of 6 November 2026)."""
    if any(v.kind in HARD_KINDS for v in extract_values(text, lang)):
        return True
    return len(stems(text, lang.partition("-")[0])) >= _SPECIFIC_STEMS


@lru_cache(maxsize=8)
def _topic_patterns(lang: str) -> tuple[re.Pattern[str], ...]:
    words = next(
        (EXAMPLE_TOPIC_WORDS[k] for k in variety_chain(lang) if k in EXAMPLE_TOPIC_WORDS), ()
    )
    # The office of the variety's own dog-tax example (varieties.toml, `prompt.office`),
    # so a variety whose example names another office than the Swiss Einwohnerkontrolle
    # is guarded the same way.
    office = variety_table(lang).prompt.get("office")
    extra = (r"\b" + re.escape(office.lower()),) if office else ()
    return tuple(re.compile(p) for p in (*words, *extra))


@lru_cache(maxsize=16)
def example_values(lang: str, stage: str) -> tuple[Value, ...]:
    """The dates, amounts, phone numbers, addresses and times of a prompt's examples
    and style guide (`044 123 45 67`, `4. Februar 2026`), one Value per canonical."""
    values: dict[tuple[str, str], Value] = {}
    for text in _static_renders(lang, stage):
        for v in extract_values(text, lang):
            if v.kind in HARD_KINDS:
                values.setdefault(v.key, v)
    return tuple(values.values())


def topic_sentences(
    texts: list[str], lang: str, source_text: str, stage: str = "write"
) -> list[str]:
    """The texts about the examples' topics, or with one of the examples' values (their
    phone numbers, dates, amounts and hours), that the source does not have. In the
    first evaluation run on CSCS the examples' phone number and date stood in 4 of 19
    P2 drafts, in sentences without a topic word (6 October 2026)."""
    source = example_key(source_text)
    patterns = [p for p in _topic_patterns(lang) if not p.search(source)]
    source_values = extract_values(source_text, lang)
    foreign = [
        v for v in example_values(lang, stage) if not any(matches(v, s) for s in source_values)
    ]

    def topical(text: str) -> bool:
        if any(p.search(example_key(text)) for p in patterns):
            return True
        return any(matches(e, v) for v in extract_values(text, lang) for e in foreign)

    return [t for t in texts if topical(t)]


def copy_check(lang: str, stage: str, texts_of):
    """A `check` for complete_json: an answer whose sentences are mostly from the prompt's
    examples (COPY_LIMIT or more, and more than half of them, one of them saying
    something of its own, `_specific`) is sent back once with a message in the
    document's language; a second copy fails the stage. A stock phrase or two that an
    honest draft shares with an example ("Haben Sie Fragen?") is no copy."""

    def check(out) -> str | None:
        texts = texts_of(out)
        copied = _copied(texts, lang, stage)
        copies = len(copied)
        if (
            copies >= COPY_LIMIT
            and copies * 2 > len(texts)
            and any(_specific(t, lang) for t in copied)
        ):
            log.warning("stage %s: the answer copies %d sentences of the example", stage, copies)
            return label(lang, "copied_example", count=copies)
        return None

    return check


def topic_check(lang: str, stage: str, texts_of, source_text: str):
    """A soft `check` for complete_json: an answer with sentences about the examples'
    topics, in a document that has none, is sent back once; what the second answer
    still has, the stage drops (`drop_topical`). One such sentence is not worth a
    failed stage: on CSCS two P1 jobs failed over a single one (6 October 2026)."""

    def check(out) -> str | None:
        topical = topic_sentences(texts_of(out), lang, source_text, stage)
        if topical:
            log.warning("stage %s: %d sentences about the examples' topics", stage, len(topical))
            return label(lang, "copied_example", count=len(topical))
        return None

    return check


def soft_checks(*checks):
    """One soft check from several: the first message wins."""

    def check(out) -> str | None:
        for c in checks:
            message = c(out)
            if message is not None:
                return message
        return None

    return check


def drop_topical(texts: list[str], lang: str, source_text: str, stage: str) -> set[str]:
    """The texts a stage drops from the answer it uses: still about the examples' topics."""
    dropped = set(topic_sentences(texts, lang, source_text, stage))
    if dropped:
        log.warning("dropping %d sentences about the examples' topics", len(dropped))
    return dropped


def understand_texts(out: UnderstandOut) -> list[str]:
    # Facts only: the short core answers ("120 francs par chien.") can coincide with the
    # example for a document on the same topic; a copied fact sheet repeats its facts.
    return [f.text for f in out.facts]


def write_texts(out: WriteOut) -> list[str]:
    return [b.text for b in out.blocks if b.kind != "heading"]


def repair_texts(out: RepairOut) -> list[str]:
    return [t for item in out.repairs for t in item.texts] + [
        t for add in out.additions for t in add.texts
    ]


def foreign_check(lang: str, known: KnownValues, texts_of):
    """A `check` for complete_json: an answer with a date, amount, phone number, e-mail
    or web address, percentage or time that neither the source nor the fact sheet
    contains (the check of rule FACT-06) is sent back with the values named. Used as a
    soft check, so the stage never fails because of it. On the Public AI 8B the repair
    additions carried the examples' phone number into 8 of 12 dev drafts (6 October
    2026)."""

    def check(out) -> str | None:
        seen: dict[str, None] = {}
        for text in texts_of(out):
            for value in known.foreign(text):
                seen.setdefault(value.text, None)
        if not seen:
            return None
        # The values themselves only at DEBUG: they are the model's words (operations.md).
        log.warning("the answer has %d values not in the document", len(seen))
        log.debug("values not in the document: %s", ", ".join(seen))
        return label(lang, "foreign_values", values=", ".join(seen))

    return check
