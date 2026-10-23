"""Interface languages of the web UI.

Every language is one JSON file in `locales/`, named by its code (`en.json`,
`de.json`). The file maps flat dotted keys to texts with `{name}` placeholders; the
key `_name` holds the language's own name for the switcher. English is the reference:
a key missing in another catalog falls back to English, and a test makes sure every
shipped catalog has exactly the English keys. Adding French or Italian means adding
`fr.json` or `it.json`; nothing else changes.

The rule checker's findings are translated as well: `rules/messages.py` holds their
English templates, the English catalog takes them over under `finding.<key>`, and the
other catalogs translate them (`finding.LEN-01`, `finding.LEN-02.sub`, ...).

A key with a count has the variants `<key>.one` and `<key>.other`, chosen by
`PLURAL_ONE`. Keys under `js.` (and the job statuses) are sent to the browser for
`app.js`, which picks the plural variant with `Intl.PluralRules`.

The interface language is the reviewer's, independent of the document's language:
a German-speaking reviewer can check a French draft in a German interface.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from leichtfacile.rules.messages import MESSAGES

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "en"
COOKIE = "ui_lang"
# The counts that take the singular form; CLDR's "one" category for integers.
PLURAL_ONE: dict[str, frozenset[int]] = {"fr": frozenset({0, 1})}


@lru_cache(maxsize=1)
def catalogs() -> dict[str, dict[str, str]]:
    """All catalogs by language code, English first."""
    found = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in LOCALES_DIR.glob("*.json")}
    # The checker's messages and the rules' titles: English from the rules package,
    # translations from the files.
    found[DEFAULT_LANG] = {**found[DEFAULT_LANG], **finding_texts(), **rule_texts()}
    order = sorted(found, key=lambda code: (code != DEFAULT_LANG, code))
    return {code: found[code] for code in order}


def finding_texts() -> dict[str, str]:
    """The English templates of the rule checker's messages as catalog entries."""
    return {f"finding.{key}": text for key, text in MESSAGES.items()}


def rule_texts() -> dict[str, str]:
    """The rules' titles (the "Rule" column of docs/rules.md) as catalog entries
    `rule.<ID>`, one per rule across its language variants."""
    from leichtfacile.rules import RULES  # importing the package registers every rule

    out: dict[str, str] = {}
    for rule_id, spec in RULES.items():
        out.setdefault(f"rule.{rule_id.removesuffix('-DE').removesuffix('-FR')}", spec.title)
    return out


def ui_languages() -> dict[str, str]:
    """Language code -> the language's own name, for the switcher."""
    return {code: cat.get("_name", code) for code, cat in catalogs().items()}


def pick_language(cookie: str | None, accept_language: str | None, default: str = "auto") -> str:
    """The interface language: the reviewer's choice (cookie), else the configured
    default, else the browser's preference, else English."""
    available = catalogs()
    if cookie in available:
        return cookie
    if default in available:
        return default
    for tag in _preferences(accept_language or ""):
        if tag in available:
            return tag
    return DEFAULT_LANG


def _preferences(header: str) -> list[str]:
    """Primary language subtags from an Accept-Language header, best first."""
    ranked: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        tag, _, params = part.strip().partition(";")
        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                quality = 0.0
        primary = tag.strip().split("-")[0].lower()
        if primary and primary != "*" and quality > 0:
            ranked.append((-quality, index, primary))
    return [tag for _, _, tag in sorted(ranked)]


class Translator:
    """`t("key", name=value)` in Python and in the templates."""

    def __init__(self, lang: str = DEFAULT_LANG) -> None:
        all_catalogs = catalogs()
        self.lang = lang if lang in all_catalogs else DEFAULT_LANG
        self._texts = all_catalogs[self.lang]
        self._fallback = all_catalogs[DEFAULT_LANG]

    def __call__(self, key: str, /, n: int | None = None, **params: object) -> str:
        key = self.variant(key, n)
        if n is not None:
            params["n"] = n
        text = self._texts.get(key) or self._fallback.get(key)
        if text is None:
            return key
        return text.format(**params) if params else text

    def variant(self, key: str, n: int | None = None) -> str:
        """The catalog key for a count: `<key>.one` or `<key>.other`; without a count,
        the key itself."""
        if n is None:
            return key
        form = "one" if n in PLURAL_ONE.get(self.lang, frozenset({1})) else "other"
        return f"{key}.{form}"

    def has(self, key: str, n: int | None = None) -> bool:
        """Whether a text exists for the key, in this language or in English."""
        key = self.variant(key, n)
        return key in self._texts or key in self._fallback

    def get(self, key: str, default: str) -> str:
        """The text for a key built from data (a status, a fact kind), else `default`."""
        return self._texts.get(key) or self._fallback.get(key) or default

    def js(self) -> dict[str, str]:
        """The texts `app.js` needs: the `js.` keys without the prefix, and the job
        statuses for the chip it updates after a save."""
        merged = {**self._fallback, **self._texts}
        return {
            k.removeprefix("js."): v for k, v in merged.items() if k.startswith(("js.", "status."))
        }


ENGLISH = Translator(DEFAULT_LANG)
