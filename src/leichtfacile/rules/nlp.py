"""spaCy pipelines for the checker, loaded once per language.

German uses de_core_news_md and French fr_core_news_md (morphologizer, parser,
lemmatizer), installed as packages or unpacked by `leichtfacile models`
(spacy_models.py); without them the checker stops with `ModelMissing` instead of
checking less. Italian has no model yet; it gets a blank pipeline with a rule-based
sentencizer, enough for readability and the language-independent rules.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import spacy
from spacy.language import Language

from leichtfacile import spacy_models

log = logging.getLogger(__name__)

# Languages without a pinned model (spacy_models.MODELS): their package when installed.
MODELS = {"it": "it_core_news_md"}


@lru_cache(maxsize=4)
def pipeline(lang: str) -> Language:
    if lang in spacy_models.MODELS:
        source = spacy_models.locate(lang)
        if source is None:
            raise spacy_models.ModelMissing(lang)
        return spacy.load(source, exclude=["ner"])
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
