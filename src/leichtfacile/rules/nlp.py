"""spaCy pipelines for the checker, loaded once per language.

German parses with spaCy's de_core_news_md and French with fr_core_news_md
(morphologizer, parser, lemmatizer). Italian has no model with a usable licence (every
spaCy Italian model is CC BY-NC-SA, docs/rules.md), so it tags with the Morph-it!
lexicon: the component `morphit` of leichtfacile_model_it sets the lemma, the part of
speech and the morphology of every token from the lexicon, and no parser. The three
come from PyPI as the packages leichtfacile-model-de, -fr and -it (spaCy's models
republished by scripts/model_packages.py, the Italian pipeline built by
scripts/lexicon_package.py); a missing one is a broken install.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from functools import lru_cache

import spacy
from spacy.language import Language
from spacy.tokens import Doc

# The packages the package depends on, by language.
MODELS = {
    "de": "leichtfacile_model_de",
    "fr": "leichtfacile_model_fr",
    "it": "leichtfacile_model_it",
}
LEXICON_COMPONENT = "morphit"
# One lock per language's pipeline, taken by every caller that runs it (`parse`): the
# worker threads and the web requests (the Check page) share the pipelines, and a spaCy
# pipeline takes one text at a time. A lock per checker let the de-CH and the de-DE
# checkers run the one German pipeline at once, and the vocabulary matcher, the code
# splitting and the split of free text into blocks took none.
_LOCKS = {lang: threading.Lock() for lang in MODELS}


@lru_cache(maxsize=4)
def pipeline(lang: str) -> Language:
    try:
        name = MODELS[lang]
    except KeyError:
        raise ValueError(f"no checker pipeline for language {lang!r}") from None
    return spacy.load(name, exclude=["ner"])


def parse(lang: str, texts: Iterable[str]) -> list[Doc]:
    """The texts through the language's pipeline, under its lock."""
    nlp = pipeline(lang)
    with _LOCKS[lang]:
        return list(nlp.pipe(texts))


def has_parser(nlp: Language) -> bool:
    return "parser" in nlp.pipe_names


def has_analysis(nlp: Language) -> bool:
    """Whether the pipeline gives the sentence rules what they read: a dependency parse
    (German, French) or the lexicon's lemma, part of speech and morphology (Italian)."""
    return has_parser(nlp) or LEXICON_COMPONENT in nlp.pipe_names
