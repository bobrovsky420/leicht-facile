"""The Mediopunkt written by code (docs/rules.md, LEX-01; docs/architecture.md §4.3).

Rule LEX-01 detects a long compound and proposes the split; this step writes it. The two
halves only work together: the 8B writer does not apply the split it is given in a
repair round (job 287fea3aadd2 on CSCS, 6 October 2026, kept `Alleinstehende` and
`Einkommensgrenze` unsplit through two rounds), and a warning alone costs a polish
round. So after the write stage and after every repair round, before the check, every
compound noun with a part longer than the level's limit gets its Mediopunkt, in the
blocks and in the glossary terms, and a capital after an existing dot is lowered.

Nouns only: spaCy tags NOUN or PROPN. Adjectives, participles and verbs
(`zivilrechtlichen`, `anspruchsberechtigt`) keep their LEX-01 warning, because the easy
language fix for them is another word, not `zivil·rechtlichen`. Tokens with a digit,
web and e-mail addresses are never touched, so no value of the fact contract can
change, and neither are the names of the fact sheet's medications (FACT-09): a reader
compares them with the package. The suggestion comes from the helper LEX-01 uses, so
rule and step agree, and the step is idempotent: a second run changes nothing.

The step runs in the conditions P1 and P2 only (orchestrator); a baseline measures the
prompt alone. The CLI `check` is untouched: it checks a text as it is.
"""

from __future__ import annotations

from collections.abc import Iterable

from spacy.language import Language
from spacy.tokens import Doc

from leichtfacile.rules.base import params_for
from leichtfacile.rules.lexicon import (
    MEDIOPUNKT,
    lowercase_after_mediopunkt,
    mediopunkt_suggestion,
)
from leichtfacile.rules.nlp import pipeline
from leichtfacile.schemas import CodeEdit, Draft

RULE_ID = "LEX-01"
GLOSSARY = "glossary"  # the block_id of an edit to a glossary term
NOUN_TAGS = frozenset({"NOUN", "PROPN"})
LANGS = ("de",)  # French has no long compounds (LEX-01-FR stays a note)


def apply_mediopunkt(draft: Draft, keep: Iterable[str] = ()) -> tuple[Draft, list[CodeEdit]]:
    """The draft with its compound nouns split, and the edits made. The edits are also
    recorded on the returned draft (`code_edits`, one entry per changed word), after
    those an earlier run recorded on the same version; a run that changes nothing
    returns the draft as it is. The words of `keep` (medication names) stay as they
    are."""
    if draft.lang not in LANGS:
        return draft, []
    limit = params_for(draft.lang, draft.level).max_word_letters
    nlp = pipeline(draft.lang)
    tagged = _has_tagger(nlp)
    kept = frozenset(word.lower() for name in keep for word in name.split())
    edits: list[CodeEdit] = []
    blocks = []
    for block, doc in zip(draft.blocks, nlp.pipe(b.text for b in draft.blocks), strict=True):
        text, changes = split_text(doc, limit, tagged, kept)
        edits += _edits(block.id, changes)
        blocks.append(block.model_copy(update={"text": text}) if changes else block)
    glossary = []
    for entry in draft.glossary:
        # A glossary term is a noun phrase by nature; the tagger is unreliable on a bare
        # phrase, so every capitalised word of the term counts as a noun.
        term, changes = split_text(nlp(entry.term), limit, tagged=False, kept=kept)
        edits += _edits(GLOSSARY, changes)
        glossary.append(entry.model_copy(update={"term": term}) if changes else entry)
    if not edits:
        return draft, []
    update = {"blocks": blocks, "glossary": glossary, "code_edits": [*draft.code_edits, *edits]}
    return draft.model_copy(update=update), edits


def _edits(block_id: str, changes: list[tuple[str, str]]) -> list[CodeEdit]:
    return [CodeEdit(block_id=block_id, rule_id=RULE_ID, before=a, after=b) for a, b in changes]


def split_text(
    doc: Doc, limit: int, tagged: bool, kept: frozenset[str] = frozenset()
) -> tuple[str, list[tuple[str, str]]]:
    """The text of a parsed block with its compound nouns split; and (before, after) per
    changed word. With `tagged` False (no tagger, or a glossary term), a capitalised
    word counts as a noun. A word of `kept` is never changed."""
    out: list[str] = []
    changes: list[tuple[str, str]] = []
    for t in doc:
        word = t.text
        if word.lower() not in kept and _candidate(t, tagged) and not _before_number(t):
            lowered = lowercase_after_mediopunkt(word)
            fixed = lowered or word
            split = mediopunkt_suggestion(fixed, limit)
            fixed = split or fixed
            if fixed != word:
                changes.append((word, fixed))
                word = fixed
        out.append(word + t.whitespace_)
    return "".join(out), changes


def _candidate(t, tagged: bool) -> bool:
    text = t.text
    if t.like_url or t.like_email or any(ch.isdigit() for ch in text):
        return False
    if not any(ch.isalpha() for ch in text):
        return False
    if MEDIOPUNKT in text and lowercase_after_mediopunkt(text):
        return True  # typography, whatever the part of speech
    if not text[:1].isupper():
        return False  # a German noun is capitalised; a lowercase NOUN tag is a tagger slip
    return t.pos_ in NOUN_TAGS if tagged else True


def _before_number(t) -> bool:
    """The word in front of a number is a street with its house number (Ostermundigen-
    strasse 99B) or a name with a count; the splitter does not know such names and
    would cut them into nonsense (Ostermundi·gens·trasse). Addresses stay as written."""
    nxt = t.nbor(1) if t.i + 1 < len(t.doc) else None
    return nxt is not None and any(ch.isdigit() for ch in nxt.text)


def _has_tagger(nlp: Language) -> bool:
    return any(name in nlp.pipe_names for name in ("tagger", "morphologizer"))
