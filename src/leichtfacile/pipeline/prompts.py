"""Prompt templates (llm/prompts/<lang>/*.md), rendered with Jinja2.

Each rendered prompt carries the version of its template, a short hash of the file, so
the audit bundle and the evaluation can say exactly which prompt produced an artifact.

`llm/prompts/en/` is no document language: it holds English instructions for German and
French documents, an experiment behind LLM_ENGLISH_PROMPTS (docs/prompts.md, "English
instructions"). The document, the examples and every text the model writes stay in the
document's language.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"
STAGES = ("understand", "write", "judge", "repair", "baseline", "baseline_zh")
ENGLISH = "en"
# The stages that have English instructions. The baselines stay what a user types.
ENGLISH_STAGES = ("understand", "write", "judge", "repair")
# The document's language as the English instructions name it.
LANGUAGE_NAMES = {"de": "German", "fr": "French"}


class PromptNotAvailable(LookupError):
    """No prompt template for this language yet."""


_env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=False,
    autoescape=False,
    trim_blocks=True,
)


def available_languages() -> list[str]:
    return sorted(
        p.name
        for p in PROMPTS_DIR.iterdir()
        if p.is_dir() and p.name != ENGLISH and (p / "write.md").exists()
    )


def has_prompt(lang: str, stage: str) -> bool:
    """Whether a template exists: the Zurich baseline (`baseline_zh`) is German only."""
    return (PROMPTS_DIR / lang / f"{stage}.md").exists()


# The level as the prompts use it after "in": German needs the dative.
_IN_LEVEL = {
    "de": {"A2": "Leichter Sprache", "B1": "Einfacher Sprache"},
    "fr": {"A2": "FALC", "B1": "langage clair"},
    "it": {"A2": "lingua facile", "B1": "linguaggio semplice"},
}
# The level as the English instructions name it: its own name and what it is.
_ENGLISH_LEVEL = {
    "de": {"A2": "Leichte Sprache (easy-to-read German)", "B1": "Einfache Sprache (plain German)"},
    "fr": {"A2": "FALC (easy-to-read French)", "B1": "langage clair (plain French)"},
}


def level_name(lang: str, level: str, english: bool = False) -> str:
    if english:
        return _ENGLISH_LEVEL[lang][level]
    return _IN_LEVEL.get(lang, _IN_LEVEL["de"])[level]


def render(lang: str, stage: str, *, english: bool = False, **context: object) -> str:
    """The prompt of a stage for a document in `lang`. With `english`, the template of
    `en/`, which gets the document's language as `lang` and `language`."""
    folder = ENGLISH if english else lang
    path = PROMPTS_DIR / folder / f"{stage}.md"
    if not path.exists() or (english and lang not in LANGUAGE_NAMES):
        raise PromptNotAvailable(
            f"no {stage} prompt for language '{lang}'"
            + (" with English instructions" if english else "")
            + f" yet (available: {available_languages()})"
        )
    if english:
        context = {**context, "lang": lang, "language": LANGUAGE_NAMES[lang]}
    return _env.get_template(f"{folder}/{stage}.md").render(**context).strip() + "\n"


@lru_cache(maxsize=64)
def prompt_version(lang: str, stage: str) -> str:
    path = PROMPTS_DIR / lang / f"{stage}.md"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else "none"


def prompt_versions(lang: str, english: Iterable[str] = ()) -> dict[str, str]:
    """The template version per stage; a stage with English instructions (`english`)
    names the English template's, as `en:<hash>`."""
    english = set(english) & set(ENGLISH_STAGES)
    return {
        stage: f"{ENGLISH}:{prompt_version(ENGLISH, stage)}"
        if stage in english
        else prompt_version(lang, stage)
        for stage in STAGES
    }


@lru_cache(maxsize=8)
def examples(lang: str) -> str:
    """Few-shot examples, written by the team (never texts from protected pages)."""
    folder = PROMPTS_DIR / lang / "examples"
    if not folder.exists():
        return ""
    parts = [p.read_text(encoding="utf-8").strip() for p in sorted(folder.glob("*.md"))]
    return "\n\n---\n\n".join(parts)
