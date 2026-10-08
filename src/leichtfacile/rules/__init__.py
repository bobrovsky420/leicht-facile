"""Deterministic rule checks (docs/rules.md).

Importing the package registers every rule: German rules in `de`, French rules in `fr`,
language-independent ones in `document` (facts, headings, readability, judge rule ids),
`decision` (decision mode), `medication` (patient letters) and `layout` (export).
"""

from leichtfacile.rules import (  # noqa: F401  (registers the rules)
    de,
    decision,
    document,
    fr,
    layout,
    medication,
)
from leichtfacile.rules.base import PARAMS, RULES, LevelParams, RuleSpec, params_for
from leichtfacile.rules.checker import RuleChecker, check_draft, get_checker
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
    "style_guide",
]
