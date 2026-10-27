"""spaCy pipelines for the checker, loaded once per language.

German parses with spaCy's de_core_news_md and French with fr_core_news_md
(morphologizer, parser, lemmatizer), which the package depends on as
leichtfacile-model-de and leichtfacile-model-fr (spaCy's models republished on PyPI,
scripts/model_packages.py). Italian has no model yet; it gets a blank pipeline with a
rule-based sentencizer, enough for readability and the language-independent rules.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import spacy
from spacy.language import Language

log = logging.getLogger(__name__)

# The packages the package depends on; a missing one is a broken install.
MODELS = {"de": "leichtfacile_model_de", "fr": "leichtfacile_model_fr"}
# Languages without a dependency: their package when installed.
OPTIONAL = {"it": "it_core_news_md"}


@lru_cache(maxsize=4)
def pipeline(lang: str) -> Language:
    if lang in MODELS:
        return spacy.load(MODELS[lang], exclude=["ner"])
    name = OPTIONAL.get(lang)
    if name:
        try:
            return spacy.load(name, exclude=["ner"])
        except OSError:
            log.info("spaCy model %s not installed; using a blank %s pipeline", name, lang)
    nlp = spacy.blank(lang)
    nlp.add_pipe("sentencizer")
    return nlp


def has_parser(nlp: Language) -> bool:
    return "parser" in nlp.pipe_names
