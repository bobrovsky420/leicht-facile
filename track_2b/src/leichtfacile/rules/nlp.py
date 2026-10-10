"""spaCy pipelines for the checker, loaded once per language.

German uses de_core_news_md and French fr_core_news_md (morphologizer, parser,
lemmatizer). Italian has no model in the image yet; it gets a blank pipeline with a
rule-based sentencizer, enough for readability and the language-independent rules.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import spacy
from spacy.language import Language

log = logging.getLogger(__name__)

MODELS = {"de": "de_core_news_md", "fr": "fr_core_news_md", "it": "it_core_news_md"}


@lru_cache(maxsize=4)
def pipeline(lang: str) -> Language:
    name = MODELS.get(lang)
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
