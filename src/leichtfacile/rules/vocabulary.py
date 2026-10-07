"""Hard words for easy language, per language: an everyday word to use instead, or a
plain explanation for the glossary when the term has to stay.

The lists are rules/data/vocabulary_{lang}.toml; their header says how to edit them.
They are the seed of the termbase (PLAN.md, WP17): hard term, easy term, explanation.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Literal

Kind = Literal["replace", "explain"]
KINDS: tuple[Kind, ...] = ("replace", "explain")


@dataclass(frozen=True)
class VocabularyEntry:
    term: str
    kind: Kind
    group: str  # connectors, verbs, law, insurance, ... (the TOML table)
    easy: str | None = None  # kind "replace": the everyday word
    explanation: str | None = None  # kind "explain": the glossary text


def vocabulary_path(lang: str):
    return resources.files("leichtfacile.rules") / "data" / f"vocabulary_{lang}.toml"


@lru_cache
def load_vocabulary(lang: str) -> tuple[VocabularyEntry, ...]:
    data = tomllib.loads(vocabulary_path(lang).read_text(encoding="utf-8"))
    unknown = set(data) - set(KINDS)
    if unknown:
        raise ValueError(f"vocabulary_{lang}.toml: unknown tables {sorted(unknown)}")
    entries = []
    for kind in KINDS:
        for group, terms in data.get(kind, {}).items():
            for term, text in terms.items():
                if kind == "replace":
                    entries.append(VocabularyEntry(term, kind, group, easy=text))
                else:
                    entries.append(VocabularyEntry(term, kind, group, explanation=text))
    return tuple(entries)
