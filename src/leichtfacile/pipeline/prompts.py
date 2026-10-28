"""Prompt templates (llm/prompts/<lang>/*.md), rendered with Jinja2.

Each rendered prompt carries the version of its template, a short hash of the file, so
the audit bundle and the evaluation can say exactly which prompt produced an artifact.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"
STAGES = ("understand", "write", "judge", "repair", "baseline", "baseline_zh")


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
    return sorted(p.name for p in PROMPTS_DIR.iterdir() if p.is_dir() and (p / "write.md").exists())


def has_prompt(lang: str, stage: str) -> bool:
    """Whether a template exists: the Zurich baseline (`baseline_zh`) is German only."""
    return (PROMPTS_DIR / lang / f"{stage}.md").exists()


# The level as the prompts use it after "in": German needs the dative.
_IN_LEVEL = {
    "de": {"A2": "Leichter Sprache", "B1": "Einfacher Sprache"},
    "fr": {"A2": "FALC", "B1": "langage clair"},
    "it": {"A2": "lingua facile", "B1": "linguaggio chiaro"},
}


def level_name(lang: str, level: str) -> str:
    return _IN_LEVEL.get(lang, _IN_LEVEL["de"])[level]


def render(lang: str, stage: str, **context: object) -> str:
    path = PROMPTS_DIR / lang / f"{stage}.md"
    if not path.exists():
        raise PromptNotAvailable(
            f"no {stage} prompt for language '{lang}' yet (available: {available_languages()})"
        )
    return _env.get_template(f"{lang}/{stage}.md").render(**context).strip() + "\n"


@lru_cache(maxsize=64)
def prompt_version(lang: str, stage: str) -> str:
    path = PROMPTS_DIR / lang / f"{stage}.md"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else "none"


def prompt_versions(lang: str) -> dict[str, str]:
    return {stage: prompt_version(lang, stage) for stage in STAGES}


@lru_cache(maxsize=8)
def examples(lang: str) -> str:
    """Few-shot examples, written by the team (never texts from protected pages)."""
    folder = PROMPTS_DIR / lang / "examples"
    if not folder.exists():
        return ""
    parts = [p.read_text(encoding="utf-8").strip() for p in sorted(folder.glob("*.md"))]
    return "\n\n---\n\n".join(parts)
