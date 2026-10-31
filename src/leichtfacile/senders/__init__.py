"""The senders a job can name (an authority, a school, another organisation) and the
forms in which a text addresses its reader (Sie, du, ihr and their French and Italian
counterparts), as data in senders.toml next to this module (docs/architecture.md
section 4.3). The prompt templates take a sender's phrases as `s` and a form's note as
`address_note` (pipeline/prompts.py); the style guide and LEX-06 take a form's guide
line and pronoun (rules/styleguide.py, rules/shared.py). This module imports nothing
heavy: the rules and the prompts read it on import.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from leichtfacile.schemas import ADDRESS_FORMS, SENDERS, base_lang

TABLE = Path(__file__).resolve().parent / "senders.toml"


@dataclass(frozen=True)
class SenderProfile:
    key: str
    label: str
    # By language: `writes`, `document`, `judged` (the file's header says where each
    # phrase goes). Left out of the hash, so a profile stays hashable.
    phrases: dict[str, dict[str, str]] = field(default_factory=dict, hash=False)

    def for_prompt(self, lang: str, facts: dict[str, str]) -> dict[str, str]:
        """The phrases of a language or variety key, with the variety's prompt facts
        filled in (German: {country_adjective}, {country_in}; varieties.toml)."""
        return {k: v.format_map(facts) for k, v in self.phrases[base_lang(lang)].items()}


@dataclass(frozen=True)
class AddressForm:
    key: str
    label: str
    forms: dict[str, dict[str, str]] = field(default_factory=dict, hash=False)

    def pronoun(self, lang: str) -> str:
        return self.forms[base_lang(lang)]["pronoun"]

    def guide(self, lang: str) -> str:
        """The style guide's line for LEX-06 in this form."""
        return self.forms[base_lang(lang)]["guide"]

    def note(self, lang: str) -> str:
        """The paragraph the write, repair and recover prompts add; "" for formal."""
        return self.forms[base_lang(lang)]["note"]


@lru_cache(maxsize=1)
def _tables() -> dict[str, dict]:
    with TABLE.open("rb") as handle:
        return tomllib.load(handle)


@lru_cache(maxsize=1)
def senders() -> dict[str, SenderProfile]:
    """The senders in the file's order; the keys are those of `schemas.Sender`."""
    found = {
        key: SenderProfile(
            key=key, label=table["label"], phrases={k: v for k, v in table.items() if k != "label"}
        )
        for key, table in _tables()["senders"].items()
    }
    if set(found) != set(SENDERS):
        raise ValueError(f"senders.toml names {sorted(found)}, the schema {sorted(SENDERS)}")
    return found


def sender(key: str) -> SenderProfile:
    try:
        return senders()[key]
    except KeyError:
        raise KeyError(f"no sender {key!r}; known: {', '.join(senders())}") from None


@lru_cache(maxsize=1)
def address_forms() -> dict[str, AddressForm]:
    """The forms of address in the file's order; the keys are `schemas.Address`."""
    found = {
        key: AddressForm(
            key=key, label=table["label"], forms={k: v for k, v in table.items() if k != "label"}
        )
        for key, table in _tables()["address"].items()
    }
    if set(found) != set(ADDRESS_FORMS):
        raise ValueError(f"senders.toml names {sorted(found)}, the schema {sorted(ADDRESS_FORMS)}")
    return found


def address_form(key: str) -> AddressForm:
    try:
        return address_forms()[key]
    except KeyError:
        raise KeyError(f"no form of address {key!r}; known: {', '.join(address_forms())}") from None
