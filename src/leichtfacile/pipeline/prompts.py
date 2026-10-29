"""Prompt templates (llm/prompts/<lang>/*.md), rendered with Jinja2.

Each rendered prompt carries the version of its template, a short hash of the file, so
the audit bundle and the evaluation can say exactly which prompt produced an artifact.

The German templates are one set for every German variety: they take the variety's
facts (the country, the currency, the office and the phone number of the examples) as
`v.prompt` from src/leichtfacile/varieties/varieties.toml, and they include the decision
and medication partials by a path `render` chooses, the variety's own partial when it
has one, else the language's.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, pass_context

from leichtfacile.rules.lexicon import hyphenated
from leichtfacile.rules.vocabulary import standard_spelling
from leichtfacile.schemas import base_lang
from leichtfacile.varieties import variety

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
STANDARD_REGIONS = ("DE", "AT")  # the varieties that write the sharp s


@pass_context
def _spelling(context, text: str) -> str:
    """The filter `spelling`: a Swiss word of the shared German templates ("ausser") in
    the spelling of the variety being rendered; unchanged for Switzerland."""
    v = context.get("v")
    return standard_spelling(text) if v is not None and v.region in STANDARD_REGIONS else text


_env.filters["spelling"] = _spelling


def available_languages() -> list[str]:
    return sorted(p.name for p in PROMPTS_DIR.iterdir() if p.is_dir() and (p / "write.md").exists())


# The stages a variety takes from its language when it has no template of its own;
# the Canton of Zurich's prompt (`baseline_zh`) is Swiss and is not inherited.
INHERITED_STAGES = ("understand", "write", "judge", "repair", "recover", "baseline")


def _folder(lang: str, stage: str) -> str:
    """The folder of a stage's template for a language or a variety key (`de-AT`): the
    variety's own when it has the template, else its language's."""
    if (PROMPTS_DIR / lang / f"{stage}.md").exists() or stage not in INHERITED_STAGES:
        return lang
    return base_lang(lang)


def has_prompt(lang: str, stage: str) -> bool:
    """Whether a template exists: the Zurich baseline (`baseline_zh`) is Swiss German
    only."""
    return (PROMPTS_DIR / _folder(lang, stage) / f"{stage}.md").exists()


# The partials the German templates include by a path in the context
# (`{% include decision_partial %}`), so that a variety can bring its own.
PARTIALS = ("decision", "medication")


def _partial(lang: str, name: str) -> str:
    """The path of a partial for a language or a variety key, as Jinja loads it: the
    variety's own (`de-AT/decision.md`) when it exists, else its language's."""
    folder = lang if (PROMPTS_DIR / lang / f"{name}.md").exists() else base_lang(lang)
    return f"{folder}/{name}.md"


# The level as the prompts use it after "in": German needs the dative.
_IN_LEVEL = {
    "de": {"A2": "Leichter Sprache", "B1": "Einfacher Sprache"},
    "fr": {"A2": "FALC", "B1": "langage clair"},
    "it": {"A2": "lingua facile", "B1": "linguaggio chiaro"},
}


def level_name(lang: str, level: str) -> str:
    return _IN_LEVEL.get(base_lang(lang), _IN_LEVEL["de"])[level]


def render(lang: str, stage: str, **context: object) -> str:
    """`lang`: a language or a variety key (schemas.variety): the variety's template
    when it has one, else its language's. The context gets the variety (`v`) and the
    paths of the partials (`decision_partial`, `medication_partial`); a caller's own
    values win, and the stages give none."""
    folder = _folder(lang, stage)
    if not (PROMPTS_DIR / folder / f"{stage}.md").exists():
        raise PromptNotAvailable(
            f"no {stage} prompt for language '{lang}' yet (available: {available_languages()})"
        )
    v = variety(lang)
    context.setdefault("v", v)
    for name in PARTIALS:
        context.setdefault(f"{name}_partial", _partial(lang, name))
    text = _env.get_template(f"{folder}/{stage}.md").render(**context).strip() + "\n"
    # The variety's compound mark: Germany and Austria read Hunde-Steuer and Binde-Strich
    # where the shared templates, the examples and the style guide write the Mediopunkt
    # (rules/lexicon.hyphenated; the Swiss rendering is untouched).
    return hyphenated(text) if v.compound_mark == "hyphen" else text


@lru_cache(maxsize=64)
def prompt_version(lang: str, stage: str) -> str:
    """A short hash of the stage's template and, for a variety whose prompt table fills
    the template (varieties.toml, `prompt`), of that table too: a changed fact changes
    the version the job records, as a changed template does."""
    path = PROMPTS_DIR / _folder(lang, stage) / f"{stage}.md"
    if not path.exists():
        return "none"
    digest = hashlib.sha256(path.read_bytes())
    table = variety(lang).prompt
    if table:
        digest.update(json.dumps(table, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()[:12]


def prompt_versions(lang: str) -> dict[str, str]:
    return {stage: prompt_version(lang, stage) for stage in STAGES}


@lru_cache(maxsize=8)
def examples(lang: str) -> str:
    """Few-shot examples, written by the team (never texts from protected pages): the
    variety's own folder, else its language's."""
    folder = PROMPTS_DIR / lang / "examples"
    if not folder.exists():
        folder = PROMPTS_DIR / base_lang(lang) / "examples"
    if not folder.exists():
        return ""
    parts = [p.read_text(encoding="utf-8").strip() for p in sorted(folder.glob("*.md"))]
    return "\n\n---\n\n".join(parts)
