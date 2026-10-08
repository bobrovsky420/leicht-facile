"""The checker's messages: the English template of every finding, by key.

A check reports a hit with the key of its message and the values for the placeholders:
`hit("LEN-01", words=23, limit=12, level="A2", evidence=sent.text)`. The key is the
rule id, with a suffix when a rule has several messages (`LEN-02.main`). The English
text goes into the Finding for the CLI, the eval reports and the repair prompt; the key
and the values travel with it, so that the web UI can show the finding in the
reviewer's language: the English interface catalog takes these templates over as
`finding.<key>`, and `web/locales/de.json` translates them. A count named `n` picks
the variant `<key>.one` or `<key>.other`, as in the interface catalogs. A test checks
that every hit names a template with exactly its placeholders and that every template
is used. Findings stored before the keys existed carry only the English text;
`recover()` reads key and values off that text with the rule's templates.
"""

from __future__ import annotations

import re
import string
from functools import cache

from leichtfacile.rules.base import Hit
from leichtfacile.schemas import Severity

# One entry per message. {found} is the text the rule objects to, {expected} the form
# the rule asks for, {limit} and {level} the threshold and the level it belongs to.
MESSAGES: dict[str, str] = {
    # -- German: sentence structure
    "LEN-01": "The sentence has {words} words; the limit for {level} is {limit}.",
    "LEN-02.sub": "Subordinate clause ('{opener}'): {clauses} clauses in one sentence. "
    "At most {limit} for {level}: one statement per sentence.",
    "LEN-02.main": "{clauses} main clauses in one sentence. At most {limit} for {level}: "
    "one statement per sentence.",
    "LEN-03": "Enumeration with {items} items: write it as a list.",
    "ORD-01": "The subject '{subject}' comes after the verb '{verb}'.",
    # -- German: grammar
    "GRAM-01": "Passive voice: '{found}'. Say who does what.",
    "GRAM-02": "Genitive '{found}': use von + dative or rephrase.",
    "GRAM-03": "Konjunktiv '{found}': write it directly.",
    "GRAM-03.condition": "Konjunktiv '{found}' as a hidden condition: write Wenn ... and the verb.",
    "GRAM-04": "Präteritum '{found}': use the Perfekt.",
    "GRAM-05": "Nominal style '{found}': use a verb.",
    "GRAM-05.abstract": "Abstract noun '{found}': a verb or a concrete word may be clearer.",
    "GRAM-05.infinitive": "Nominalised verb '{found}': use the verb.",
    "GRAM-06": "'{found}' has no clear reference: repeat the noun.",
    "GRAM-06.ambiguous": "'{found}' could mean several nouns ({options}): repeat the noun.",
    "GRAM-07": "Indirect speech ('{found}').",
    "GRAM-07.reported": "Reported statement ('{found}').",
    "GRAM-08": "'{found}' is a separable verb written as one word: in a main clause the "
    "prefix goes to the end ({expected}).",
    # -- German: negation
    "NEG-01": "Double negation: {found}.",
    "NEG-02": "Negation '{found}': can it be said positively?",
    # -- German: words
    "LEX-01": "'{found}' is long ({letters} letters, limit {limit}): split it with a Mediopunkt.",
    "LEX-01.lowercase": "After the Mediopunkt continue in lowercase: '{found}'.",
    "LEX-01.no_compound": "'{found}' is long ({letters} letters): use a shorter word if "
    "there is one.",
    "LEX-02": "Abbreviation '{found}': write the word in full.",
    "LEX-02.weekdays": "Abbreviated weekdays '{found}': write Montag bis Freitag.",
    "LEX-02.explained": "Abbreviation '{found}' is explained, but easy language avoids "
    "abbreviations: use the full word if you can.",
    "LEX-02.acronym": "Abbreviation '{found}': explain it or write it in full.",
    "LEX-03": "Rare word '{found}': use a common word or explain it.",
    "LEX-04": "Rare punctuation '{found}'.",
    "LEX-04.slash": "Slash between words: write und or oder.",
    "LEX-05": "Gender sign in '{found}': write both forms.",
    "LEX-05.participle": "Participle form '{found}': write the concrete persons (for example "
    "Mitarbeiterinnen und Mitarbeiter).",
    "LEX-06": "'{found}' talks about the reader in the third person: write Sie.",
    "LEX-06.no_address": "'{found}' talks about the reader in the third person: write Sie. "
    "Easy language talks to the reader directly.",
    "LEX-07": "Office word '{found}': simpler is {easy}.",
    # -- German: numbers, dates, times, amounts
    "NUM-01": "Number word '{found}': write the digit.",
    "NUM-01.ordinal": "Ordinal word '{found}': write the digit.",
    "NUM-02": "Large number '{found}': use the Swiss thousands separator.",
    "NUM-03": "Numeric date '{found}': write the month as a word.",
    "NUM-04": "Time '{found}': write it as {expected}.",
    "NUM-04.range": "Time range '{found}': write bis.",
    "NUM-05": "Duration '{found}': write hours and minutes as words.",
    "NUM-06": "Percent sign: write Prozent.",
    "NUM-07": "Amount '{found}': write {expected}.",
    "NUM-08": "Phone number '{found}': write it as {expected}.",
    # -- German: Swiss spelling
    "CH-01": "'{found}': Swiss spelling uses ss.",
    "CH-02": "Quotation marks: leave them out.",
    "CH-03": "'{found}' is German German: Swiss texts write {swiss}.",
    # -- French: sentence structure
    "LEN-01-FR": "The sentence has {words} words; the limit for {level} is {limit}.",
    "LEN-02-FR.sub": "Subordinate clause ('{opener}'): {clauses} clauses in one sentence. "
    "At most {limit} for {level}: one statement per sentence.",
    "LEN-02-FR.main": "{clauses} main clauses in one sentence. At most {limit} for {level}: "
    "one statement per sentence.",
    "LEN-03-FR": "Enumeration with {items} items: write it as a list.",
    "LEN-03-FR.commas": "Enumeration with 3 or more items: write it as a list.",
    # -- French: grammar
    "GRAM-01-FR": "Passive voice: '{found}'. Say who does what.",
    "GRAM-01-FR.state": "Passive voice or a state: '{found}'. If someone does something, say who.",
    "GRAM-03-FR": "Subjunctive '{found}': write it directly.",
    "GRAM-03-FR.after": "Subjunctive after '{reason}' ('{found}'): write two sentences.",
    "GRAM-03-FR.conditional": "Conditional '{found}': write it directly (vous devez, vous pouvez).",
    "GRAM-04-FR": "Futur simple '{found}': use aller + infinitive or the present.",
    "GRAM-04-FR.passe_simple": "Passé simple '{found}': use the passé composé.",
    "GRAM-05-FR": "Nominal style '{found}': use a verb.",
    "GRAM-05-FR.abstract": "Abstract noun '{found}': a verb or a concrete word may be clearer.",
    "GRAM-06-FR": "'{found}' has no clear reference: repeat the noun.",
    "GRAM-06-FR.ambiguous": "'{found}' could mean several nouns ({options}): repeat the noun.",
    "GRAM-07-FR": "Reported statement ('{found}'): say who says what.",
    "GRAM-08-FR": "Impersonal '{found}': say who does what (vous devez ...).",
    "GRAM-08-FR.soft": "Impersonal '{found}': say who does what, if you can.",
    # -- French: negation
    "NEG-01-FR": "Double negation: {found}.",
    "NEG-02-FR": "Negation '{found}': can it be said positively?",
    # -- French: words
    "LEX-01-FR": "'{found}' is long ({letters} letters): use a shorter word if there is one.",
    "LEX-02-FR": "Abbreviation '{found}': write the word in full.",
    "LEX-02-FR.weekdays": "Abbreviated weekdays '{found}': write du lundi au vendredi.",
    "LEX-02-FR.explained": "Abbreviation '{found}' is explained, but easy language avoids "
    "abbreviations: use the full word if you can.",
    "LEX-02-FR.acronym": "Abbreviation '{found}': explain it or write it in full.",
    "LEX-03-FR": "Rare word '{found}': use a common word or explain it.",
    "LEX-04-FR": "Rare punctuation '{found}'.",
    "LEX-04-FR.slash": "Slash between words: write et or ou.",
    "LEX-05-FR": "Inclusive form '{found}': write both forms or a neutral word.",
    "LEX-06-FR": "'{found}' talks about the reader in the third person: write vous.",
    "LEX-06-FR.no_address": "'{found}' talks about the reader in the third person: write vous. "
    "Easy language talks to the reader directly.",
    "LEX-07-FR": "Office word '{found}': simpler is {easy}.",
    # -- French: numbers, dates, times, amounts
    "NUM-01-FR": "Number word '{found}': write the digit.",
    "NUM-01-FR.ordinal": "Ordinal word '{found}': write the digit.",
    "NUM-01-FR.compound": "Number word '{found}': write the digits.",
    "NUM-02-FR": "Large number '{found}': separate the thousands with a space.",
    "NUM-03-FR": "Numeric date '{found}': write the month as a word.",
    "NUM-04-FR": "Time '{found}': write it as {expected}.",
    "NUM-04-FR.range": "Time range '{found}': write de ... à ....",
    "NUM-05-FR": "Duration '{found}': write hours and minutes as words.",
    "NUM-06-FR": "Percent sign: write pour cent.",
    "NUM-07-FR": "Amount '{found}': write {expected}.",
    "NUM-08-FR": "Phone number '{found}': write it as {expected}.",
    # -- French: Swiss usage
    "CH-03-FR": "'{found}': Swiss texts write {swiss}.",
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
}


def variant(key: str, params: dict[str, str | int | float]) -> str:
    """The template for a key: `<key>.one` or `<key>.other` when the values carry a
    count `n` (English plural: one for 1), else the key itself."""
    if "n" not in params:
        return key
    return f"{key}.{'one' if params['n'] == 1 else 'other'}"


@cache
def _pattern(key: str) -> re.Pattern[str]:
    """A regex that reads the values back off a message written from the template."""
    parts = []
    for literal, name, _spec, _conversion in string.Formatter().parse(MESSAGES[key]):
        parts.append(re.escape(literal))
        if name:
            parts.append(f"(?P<{name}>.+?)")
    return re.compile("^" + "".join(parts) + "$", re.DOTALL)


def recover(rule_id: str, message: str) -> tuple[str, dict[str, str | int]] | None:
    """Key and values of an English message that an older checker stored without them,
    matched against the templates of its rule. None when no template fits (the text
    changed since, or the rule has none)."""
    best: tuple[int, str, dict[str, str]] | None = None
    for key in MESSAGES:
        if key.split(".")[0] != rule_id:
            continue
        match = _pattern(key).match(message)
        if match is None:
            continue
        # The most specific template wins: "3 or more items" is the all-literal message,
        # not the counted one with "3 or more" as its count.
        literal = len(message) - sum(len(value) for value in match.groupdict().values())
        if best is None or literal > best[0]:
            best = (literal, key, match.groupdict())
    if best is None:
        return None
    _, key, found = best
    params: dict[str, str | int] = dict(found)
    if key.endswith((".one", ".other")):  # a plural variant: back to the key with n
        key = key.rsplit(".", 1)[0]
        count = str(params["n"])
        params["n"] = int(count) if count.isdigit() else count
    return key, params


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
    """One occurrence of a rule: the English message for `key`, filled with `params`,
    which the Hit carries along with the key for translation."""
    return Hit(
        MESSAGES[variant(key, params)].format(**params),
        evidence=evidence,
        suggestion=suggestion,
        severity=severity,
        fact_id=fact_id,
        segment_ids=segment_ids,
        block_id=block_id,
        key=key,
        params=dict(params),
    )
