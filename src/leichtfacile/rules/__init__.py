"""Deterministic rule checks (docs/rules.md).

Importing the package registers every rule: the language rules are declared in
`catalog` and get their checks from `de`, `fr` and `shared` (the checks both languages
share); the language-independent ones declare themselves in `document` (facts,
headings, readability, judge rule ids), `decision` (decision mode), `medication`
(patient letters) and `layout` (export).
"""

from leichtfacile.rules import (  # noqa: F401  (registers the rules, in this order)
    catalog,
    de,
    decision,
    document,
    fr,
    layout,
    lists,
    medication,
    shared,
)
from leichtfacile.rules.base import PARAMS, RULES, LevelParams, RuleSpec, params_for
from leichtfacile.rules.checker import RuleChecker, check_draft, get_checker, source_as_draft
from leichtfacile.rules.styleguide import style_guide

__all__ = [
    "PARAMS",
    "RULES",
    "LevelParams",
    "RuleChecker",
    "RuleSpec",
    "check_draft",
    "get_checker",
    "params_for",
    "source_as_draft",
    "style_guide",
]
