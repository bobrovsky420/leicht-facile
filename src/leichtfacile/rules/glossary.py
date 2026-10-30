"""Glossary entries written by code, from the vocabulary (rules/vocabulary.py).

The writer is asked to explain the hard words it uses and to take the explanations from
the fact sheet, but the 8B leaves many out: on the CSCS dev run of 7 October 2026 the
fact sheet of sg-el-costs-de listed Franchise, Selbstbehalt and Spitex, and the final
glossary had none of them. So after the write stage and after every repair round, before
the check, a term the vocabulary explains that a block uses and the glossary lacks gets
the vocabulary's entry: a checked explanation in easy language, the same in every draft.

Not every term: only the hard ones (`vocabulary.is_hard`), never the context-dependent
ones, at most MAX_ADDED per version and up to MAX_GLOSSARY entries in all, the rarest
first, so a short letter does not end in a dictionary. Each entry is recorded as a code
edit (rule SEM-05, the judge's question for a hard word without explanation) and marked
`origin="vocabulary"`, so the reviewer sees what code added. Like the Mediopunkt step,
it runs in the conditions P1 and P2 only and is idempotent.
"""

from __future__ import annotations

from leichtfacile.rules.vocabulary import (
    VocabularyEntry,
    explained_term,
    has_vocabulary,
    is_hard,
    matcher,
    rarity,
)
from leichtfacile.schemas import CodeEdit, Draft, GlossaryEntry

RULE_ID = "SEM-05"
GLOSSARY = "glossary"  # the block_id of an edit to the glossary (as in rules/mediopunkt.py)
MAX_ADDED = 6  # entries code adds to one version
MAX_GLOSSARY = 10  # code adds nothing to a glossary this long


def explained_terms(draft: Draft) -> set[str]:
    """The vocabulary terms the glossary already explains: named by an entry as a
    whole (Prämien·verbilligung, Invalidenversicherung (IV)) or inside its term."""
    if not has_vocabulary(draft.variety):
        return set()
    terms: set[str] = set()
    m = matcher(draft.variety)
    for g in draft.glossary:
        entry = explained_term(g.term, draft.variety)
        if entry is not None:
            terms.add(entry.term)
        terms |= {match.entry.term for match in m.find_text(g.term)}
    return terms


def unexplained_terms(draft: Draft) -> list[VocabularyEntry]:
    """The hard terms the blocks use and the glossary does not explain, in text order."""
    if not has_vocabulary(draft.variety):
        return []
    explained = explained_terms(draft)
    seen: dict[str, VocabularyEntry] = {}
    for matches in matcher(draft.variety).find_texts(b.text for b in draft.blocks):
        for match in matches:
            entry = match.entry
            if (
                entry.kind == "explain"
                and not entry.context
                and entry.term not in explained
                and is_hard(entry, draft.variety)
            ):
                seen.setdefault(entry.term, entry)
    return list(seen.values())


def fill_glossary(draft: Draft) -> tuple[Draft, list[CodeEdit]]:
    """The draft with the vocabulary's entries for the hard terms it uses unexplained,
    and the edits made (also recorded on the returned draft, after the earlier ones)."""
    room = min(MAX_ADDED, MAX_GLOSSARY - len(draft.glossary))
    missing = unexplained_terms(draft) if room > 0 else []
    if not missing:
        return draft, []
    order = {entry.term: i for i, entry in enumerate(missing)}
    chosen = sorted(missing, key=lambda e: rarity(e, draft.variety))[:room]
    chosen.sort(key=lambda e: order[e.term])  # the reader meets them in text order
    entries = [
        GlossaryEntry(term=e.term, explanation=e.explanation or "", origin="vocabulary")
        for e in chosen
    ]
    edits = [CodeEdit(block_id=GLOSSARY, rule_id=RULE_ID, before="", after=e.term) for e in chosen]
    update = {
        "glossary": [*draft.glossary, *entries],
        "code_edits": [*draft.code_edits, *edits],
    }
    return draft.model_copy(update=update), edits
