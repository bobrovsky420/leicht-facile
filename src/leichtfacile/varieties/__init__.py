"""The national varieties of the document languages: Swiss German, French and Italian,
and German for Germany and Austria (docs/architecture.md section 8).

A variety is looked up by its key (`schemas.variety`: `de-CH`, `de-DE`, `de-AT`,
`fr-CH`, `it-CH`); a bare language code names its Swiss variety, and a key without a
table of its own (`fr-DE`: French is Swiss whatever the installation's region) resolves
to its language's Swiss table. The facts come from varieties.toml next to this module,
those the German prompt templates take among them (`prompt`); a variety is offered to
the user (`leichtfacile setup`) only when its prompts exist, which `complete` decides
from the prompt folders. This module imports nothing heavy: the settings and the setup
command read it before any model or spaCy pipeline is loaded.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from leichtfacile.schemas import REGIONS, base_lang, canonical_variety
from leichtfacile.schemas import variety as variety_key

TABLE = Path(__file__).resolve().parent / "varieties.toml"
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"


@dataclass(frozen=True)
class Variety:
    key: str
    lang: str
    region: str
    label: str
    word_lang: str  # the Word export's language tag
    hyphenation: str  # pyphen's dictionary
    notice: str  # the decision mode's default notice
    setup_label: str | None = None  # the choice setup offers; German varieties only
    # How a long compound is split in the variety's texts: mediopunkt (Kranken·kasse) or
    # hyphen (Kranken-Kasse), docs/rules.md LEX-01; the German varieties set it.
    compound_mark: str = "mediopunkt"
    # The facts the German prompt templates take as `v.prompt` (pipeline/prompts.py);
    # French and Italian have none. Left out of the hash, so a Variety stays hashable.
    prompt: dict[str, str] = field(default_factory=dict, hash=False)


@lru_cache(maxsize=1)
def varieties() -> dict[str, Variety]:
    with TABLE.open("rb") as handle:
        tables = tomllib.load(handle)
    return {key: Variety(key=key, **table) for key, table in tables.items()}


def variety(key: str, region: str | None = None) -> Variety:
    """The variety of a key (`de-AT`; a bare `de` is `de-CH`) or of a language and a
    region; a key without a table of its own falls back to its language's Swiss table."""
    if region is not None:
        key = variety_key(key, region)
    key = canonical_variety(key)
    table = varieties()
    found = table.get(key) or table.get(variety_key(base_lang(key)))
    if found is None:
        raise KeyError(f"no variety {key!r}; known: {', '.join(table)}")
    return found


def complete(key: str) -> bool:
    """Whether the variety's prompts exist: a prompt folder of its own with the write
    template, or its language's templates (prompts/de/write.md, one set for every
    variety of the language) with a folder of its own few-shot examples
    (prompts/de-AT/examples)."""
    key = canonical_variety(key)
    folder = PROMPTS_DIR / key
    if (folder / "write.md").exists():
        return True
    return (PROMPTS_DIR / base_lang(key) / "write.md").exists() and any(
        (folder / "examples").glob("*.md")
    )


def regions(lang: str = "de") -> tuple[str, ...]:
    """The regions whose variety of the language has a table and its prompts, in the
    order of REGIONS: what `leichtfacile setup` offers."""
    return tuple(
        r for r in REGIONS if variety_key(lang, r) in varieties() and complete(variety_key(lang, r))
    )


def region_for(lang: str, region: str) -> str:
    """The region an artifact of a language carries under the installation's setting:
    the setting for German, CH for French and Italian, which have no other variety."""
    return region if lang == "de" else "CH"
