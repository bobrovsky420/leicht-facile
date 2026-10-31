"""The checker's messages: the English template of every finding, by key.

A check reports a hit with the key of its message and the values for the placeholders:
`hit("LEN-01", words=23, limit=12, level="A2", evidence=sent.text)`. The key is the
rule id, with a suffix when a rule has several messages (`LEN-02.main`). A Finding
carries the key and the values, nothing else: `render` gives the English text (the CLI,
the eval reports, the repair prompt), and the web UI shows the finding in the reviewer's
language, since the English interface catalog takes these templates over as
`finding.<key>` and `web/locales/de.json` translates them. A count named `n` picks the
variant `<key>.one` or `<key>.other`, the plural rule of the language deciding
(`plural_form`). A test checks that every hit names a template with exactly its
placeholders and that every template is used. `legacy` is the one template no rule
uses: findings stored before the keys existed (October 2026) carry their English text
as its value.
"""

from __future__ import annotations

from leichtfacile.rules.base import Hit
from leichtfacile.schemas import Finding, Severity

# The counts that take the singular form, by language; CLDR's "one" category for
# integers. English and German: 1; French: 0 and 1.
PLURAL_ONE: dict[str, frozenset[int]] = {"fr": frozenset({0, 1})}

# One entry per message. {found} is the text the rule objects to, {expected} the form
# the rule asks for, {limit} and {level} the threshold and the level it belongs to.
MESSAGES: dict[str, str] = {
    # -- sentence structure (LEN, ORD)
    "LEN-01": "The sentence has {words} words; the limit for {level} is {limit}.",
    "LEN-02.sub": "Subordinate clause ('{opener}'): {clauses} clauses in one sentence. "
    "At most {limit} for {level}: one statement per sentence.",
    "LEN-02.main": "{clauses} main clauses in one sentence. At most {limit} for {level}: "
    "one statement per sentence.",
    "LEN-03": "Enumeration with {items} items: write it as a list.",
    "LEN-03.commas": "Enumeration with 3 or more items: write it as a list.",
    "ORD-01": "The subject '{subject}' comes after the verb '{verb}'.",
    # -- grammar
    "GRAM-01": "Passive voice: '{found}'. Say who does what.",
    "GRAM-01.state": "Passive voice or a state: '{found}'. If someone does something, say who.",
    "GRAM-01.si": "Passive with si: '{found}'. Say who does what.",
    "GRAM-02": "Genitive '{found}': use von + dative or rephrase.",
    # {mood}: Konjunktiv (German), Subjonctif (French)
    "GRAM-03": "{mood} '{found}': write it directly.",
    "GRAM-03.condition": "Konjunktiv '{found}' as a hidden condition: write Wenn ... and the verb.",
    "GRAM-03.after": "Subjunctive after '{reason}' ('{found}'): write two sentences.",
    "GRAM-03.conditional": "Conditional '{found}': write it directly.",
    "GRAM-04": "Präteritum '{found}': use the Perfekt.",
    "GRAM-04.future": "Futur simple '{found}': use aller + infinitive or the present.",
    "GRAM-04.passe_simple": "Passé simple '{found}': use the passé composé.",
    "GRAM-04.passato_remoto": "Passato remoto '{found}': use the passato prossimo.",
    "GRAM-04.futuro": "Future '{found}': the present is simpler (Lei riceve).",
    "GRAM-05": "Nominal style '{found}': use a verb.",
    "GRAM-05.abstract": "Abstract noun '{found}': a verb or a concrete word may be clearer.",
    "GRAM-05.infinitive": "Nominalised verb '{found}': use the verb.",
    "GRAM-06": "'{found}' has no clear reference: repeat the noun.",
    "GRAM-06.ambiguous": "'{found}' could mean several nouns ({options}): repeat the noun.",
    "GRAM-07": "Reported speech ('{found}'): say who says what.",
    "GRAM-07.reported": "Reported statement ('{found}').",
    "GRAM-08": "'{found}' is a separable verb written as one word: in a main clause the "
    "prefix goes to the end ({expected}).",
    "GRAM-09": "Impersonal '{found}': say who does what.",
    "GRAM-09.soft": "Impersonal '{found}': say who does what, if you can.",
    "GRAM-10": "Gerund '{found}': write a sentence with its own subject and verb.",
    # -- negation
    "NEG-01": "Double negation: {found}.",
    "NEG-02": "Negation '{found}': can it be said positively?",
    # -- words
    "LEX-01": "'{found}' is long ({letters} letters, limit {limit}): split it with a Mediopunkt.",
    "LEX-01.lowercase": "After the Mediopunkt continue in lowercase: '{found}'.",
    "LEX-01.hyphen": "'{found}' is long ({letters} letters, limit {limit}): split it with a "
    "hyphen.",
    "LEX-01.mark": "'{found}': in Germany and Austria a compound is split with a hyphen: "
    "{expected}.",
    "LEX-01.no_compound": "'{found}' is long ({letters} letters): use a shorter word if "
    "there is one.",
    "LEX-02": "Abbreviation '{found}': write the word in full.",
    "LEX-02.weekdays": "Abbreviated weekdays '{found}': write {expected}.",
    "LEX-02.explained": "Abbreviation '{found}' is explained, but easy language avoids "
    "abbreviations: use the full word if you can.",
    "LEX-02.acronym": "Abbreviation '{found}': explain it or write it in full.",
    "LEX-03": "Rare word '{found}': use a common word or explain it.",
    "LEX-04": "Rare punctuation '{found}'.",
    "LEX-04.slash": "Slash between words: write {first} or {second}.",
    "LEX-05": "Gender sign in '{found}': write both forms.",
    "LEX-05.participle": "Participle form '{found}': write the concrete persons (for example "
    "Mitarbeiterinnen und Mitarbeiter).",
    "LEX-05.inclusive": "Inclusive form '{found}': write both forms or a neutral word.",
    "LEX-06": "'{found}' talks about the reader in the third person: write {address}.",
    "LEX-06.no_address": "'{found}' talks about the reader in the third person: write "
    "{address}. Easy language talks to the reader directly.",
    "LEX-07": "Office word '{found}': simpler is {easy}.",
    # -- numbers, dates, times, amounts
    "NUM-01": "Number word '{found}': write the digit.",
    "NUM-01.ordinal": "Ordinal word '{found}': write the digit.",
    "NUM-01.compound": "Number word '{found}': write the digits.",
    "NUM-02": "Large number '{found}': write {expected}.",
    "NUM-03": "Numeric date '{found}': write the month as a word.",
    "NUM-04": "Time '{found}': write it as {expected}.",
    "NUM-04.range": "Time range '{found}': write {expected}.",
    "NUM-05": "Duration '{found}': write hours and minutes as words.",
    "NUM-06": "Percent sign: write {expected}.",
    "NUM-07": "Amount '{found}': write {expected}.",
    "NUM-08": "Phone number '{found}': write it as {expected}.",
    "NUM-08.grouped": "Phone number '{found}': write the digits in groups: {expected}.",
    # -- the region: the Swiss checks, and those of Germany and Austria (29 October 2026)
    "REG-01": "'{found}': Swiss spelling uses ss.",
    "REG-01.standard": "'{found}': standard German spelling writes {expected}.",
    "REG-02": "Quotation marks: leave them out.",
    "REG-02.standard": "Quotation marks {found}: in German texts only „ “, for direct speech.",
    "REG-03": "'{found}': Swiss texts write {swiss}.",
    "REG-03.germany": "'{found}': in Germany one writes {expected}.",
    "REG-03.austria": "'{found}': in Austria one writes {expected}.",
    # -- facts (every language)
    "FACT-01": "Fact {fact} is missing or changed: {text} (expected {expected}).",
    "FACT-02": "No block conveys fact {fact}: {text}",
    "FACT-03": "The block names no source sentence.",
    "FACT-03.unknown": "The block names no source sentence (unknown ids: {ids}).",
    "FACT-04": "Source sentences {first} to {last} are neither used nor listed as omitted.",
    "FACT-04.single": "Source sentence {sentence} is neither used nor listed as omitted.",
    "FACT-05": "Fact {fact}: the value {value} is not in the source. The fact sheet may be wrong.",
    "FACT-05.cited": "Fact {fact}: the value {value} is in the source, but not in the cited "
    "sentences.",
    "FACT-05.unknown": "Fact {fact} cites unknown source sentences: {ids}.",
    # FACT-06 has one message per kind of value (values.HARD_KINDS), so that every
    # language can name the kind in its own words.
    "FACT-06.date": "The date {value} is not in the source. Remove it or take the value from "
    "the source.",
    "FACT-06.amount": "The amount {value} is not in the source. Remove it or take the value "
    "from the source.",
    "FACT-06.phone": "The phone number {value} is not in the source. Remove it or take the "
    "value from the source.",
    "FACT-06.email": "The e-mail address {value} is not in the source. Remove it or take the "
    "value from the source.",
    "FACT-06.url": "The web address {value} is not in the source. Remove it or take the value "
    "from the source.",
    "FACT-06.percent": "The percentage {value} is not in the source. Remove it or take the "
    "value from the source.",
    "FACT-06.time": "The time {value} is not in the source. Remove it or take the value from "
    "the source.",
    "FACT-06.period": "The period {value} is not in the source. Remove it or take the value "
    "from the source.",
    "FACT-06.identifier": "The reference or account number {value} is not in the source. "
    "Remove it or take the value from the source.",
    "FACT-06.address": "The address {value} is not in the source. Remove it or take the value "
    "from the source.",
    "FACT-06.quantity": "The quantity {value} is not in the source. Remove it or take the value "
    "from the source.",
    "FACT-06.schedule": "The dosing scheme {value} is not in the source. Remove it or take the "
    "value from the source.",
    # FACT-07 (decision mode, on the export): the authority's fixed notice.
    "FACT-07.first": "The export does not begin with the fixed notice: {notice}",
    "FACT-07.last": "The export does not end with the fixed notice: {notice}",
    # FACT-08 (decision mode): the operative part, item by item, and the appeal
    # instructions; `item` counts the protected parts in document order.
    "FACT-08": "Item {item} of the operative part is in no block: {text}",
    "FACT-08.omitted": "Item {item} of the operative part is listed as omitted: {text}",
    "FACT-08.appeal": "The appeal instructions are in no block: {text}",
    "FACT-08.appeal_omitted": "The appeal instructions are listed as omitted: {text}",
    # FACT-10 (rules/lists.py): an item of a list of the source.
    "FACT-10": "The list item is in no block: {text}",
    "FACT-10.omitted": "The list item is listed as omitted: {text}",
    # FACT-09 (patient letters): a medication with its dose, scheme and duration.
    "FACT-09": "{name} is named here without {values}, which another block has. Write the "
    "medication with its dose, scheme and duration in one block, one list item per "
    "medication.",
    # -- layout and readability (every language)
    "LAY-01": "Line {line} has more than one sentence.",
    "LAY-02": "Line {line} has {chars} characters; at most {limit}.",
    "LAY-03": "Heading with {words} words; at most {limit}.",
    "LAY-03.few.one": "{n} heading for {blocks} blocks: add headings, ideally as the reader's "
    "questions.",
    "LAY-03.few.other": "{n} headings for {blocks} blocks: add headings, ideally as the "
    "reader's questions.",
    "READ-01": "{formula} readability {score}.",
    "READ-01.below": "{formula} readability {score} is below the target {target} for {level}.",
    # -- findings stored before the keys existed: their English text as the value
    "legacy": "{text}",
}


def plural_form(lang: str, n: int | float | str) -> str:
    """`one` or `other` for a count, by the language's rule (English for an unknown one)."""
    try:
        count: int | float = int(n) if not isinstance(n, int | float) else n
    except ValueError:
        return "other"
    return "one" if count in PLURAL_ONE.get(lang, frozenset({1})) else "other"


def variant(key: str, params: dict[str, str | int | float], lang: str = "en") -> str:
    """The template for a key: `<key>.one` or `<key>.other` when the values carry a
    count `n`, else the key itself."""
    if "n" not in params:
        return key
    return f"{key}.{plural_form(lang, params['n'])}"


def render(key: str, params: dict[str, str | int | float]) -> str:
    """The English text of a message."""
    return MESSAGES[variant(key, params)].format(**params)


def render_finding(finding: Finding) -> str:
    return render(finding.key, finding.params)


def hit(
    key: str,
    /,
    *,
    evidence: str = "",
    suggestion: str | None = None,
    severity: Severity | None = None,
    fact_id: str | None = None,
    segment_ids: tuple[str, ...] = (),
    block_id: str | None = None,
    **params: str | int | float,
) -> Hit:
    """One occurrence of a rule: the message `key` with its `params`, which must name a
    template (a KeyError here is a slip in the check)."""
    MESSAGES[variant(key, params)]
    return Hit(
        key,
        dict(params),
        evidence=evidence,
        suggestion=suggestion,
        severity=severity,
        fact_id=fact_id,
        segment_ids=segment_ids,
        block_id=block_id,
    )
