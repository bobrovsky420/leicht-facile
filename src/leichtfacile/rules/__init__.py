"""Deterministic rule checks (docs/rules.md).

Importing the package registers every rule: German rules in `de`, French rules in `fr`,
language-independent ones in `document` (facts, headings, readability, judge rule ids)
and `layout` (export).
"""

from leichtfacile.rules import de, document, fr, layout  # noqa: F401  (registers the rules)
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
