"""Interface languages of the web UI.

Every language is one JSON file in `locales/`, named by its code (`en.json`,
`de.json`). The file maps flat dotted keys to texts with `{name}` placeholders; the
key `_name` holds the language's own name for the switcher. English is the reference:
a key missing in another catalog falls back to English, and a test makes sure every
shipped catalog has exactly the English keys. A further language is one more file,
`<code>.json`; nothing else changes.

The catalogs are written for Switzerland. The installation's region (`texts.region`)
renders the German catalog for Germany and Austria: first in their spelling, with the
sharp s of the table the vocabulary uses (`rules.vocabulary.standard_spelling`,
rules/data/spelling_de.toml: grösser becomes größer), then with the overlay of the
variety on top, a file next to the catalogs named by the variety's key: `de-DE.json`
holds only the texts whose words Germany says differently (Entscheidung for the
reviewer's decision, Bescheid for the decision letter), `de-AT.json` only those
Austria says differently from Germany, and its key `_inherits` names the overlay
below it. A German interface in Austria thus looks a text up in de-AT.json, then
de-DE.json, then de.json in the standard spelling, then English. An overlay is no
language of its own, so the switcher shows one German. The region also names the
country in the texts that mention it (`{country}`, `{spelling}`), writes the
thousands of a count as the variety does (`js.thousands`, 1.960 in Germany), and
names the variety of a German document (`lang.de-DE`) where it is not Swiss.

The rule checker's findings are translated as well: `rules/messages.py` holds their
English templates, the English catalog takes them over under `finding.<key>`, and the
other catalogs translate them (`finding.LEN-01`, `finding.LEN-02.sub`, ...).

A key with a count has the variants `<key>.one` and `<key>.other`, chosen by the
language's plural rule (`rules/messages.plural_form`, the one rule for the findings and
the interface). Keys under `js.` (and the job statuses) are sent to the browser for
`app.js`, which picks the plural variant with `Intl.PluralRules`.

The interface language is the reviewer's, independent of the document's language:
a German-speaking reviewer can check a French draft in a German interface.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from leichtfacile.rules.messages import MESSAGES, plural_form
from leichtfacile.rules.vocabulary import standard_spelling
from leichtfacile.schemas import variety

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LANG = "en"
COOKIE = "ui_lang"
INHERITS = "_inherits"  # the key of an overlay that names the overlay it builds on


@lru_cache(maxsize=1)
def _files() -> dict[str, dict[str, str]]:
    """Every file in locales/ by its name: the catalogs (`de`) and the overlays (`de-DE`)."""
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in LOCALES_DIR.glob("*.json")}


@lru_cache(maxsize=1)
def catalogs() -> dict[str, dict[str, str]]:
    """All catalogs by language code, English first; the overlays are no languages."""
    found = {code: texts for code, texts in _files().items() if "-" not in code}
    # The checker's messages and the rules' titles: English from the rules package,
    # translations from the files.
    found[DEFAULT_LANG] = {**found[DEFAULT_LANG], **finding_texts(), **rule_texts()}
    order = sorted(found, key=lambda code: (code != DEFAULT_LANG, code))
    return {code: found[code] for code in order}


@lru_cache(maxsize=1)
def overlays() -> dict[str, dict[str, str]]:
    """The overlays of the national varieties by key (`de-DE`, `de-AT`): the texts whose
    words differ from the language's catalog, and `_inherits` where an overlay builds
    on another one."""
    return {code: texts for code, texts in _files().items() if "-" in code}


def overlay_chain(key: str) -> list[str]:
    """The overlays a variety reads, its own first: `de-AT`, `de-DE` for Austria; none
    for a Swiss variety (`de-CH`) or one without an overlay (`fr-DE`)."""
    chain: list[str] = []
    while key in overlays() and key not in chain:
        chain.append(key)
        key = overlays()[key].get(INHERITS, "")
    return chain


@lru_cache(maxsize=16)
def variety_catalog(lang: str, region: str = "CH") -> dict[str, str]:
    """The texts of an interface language as the variety of a region writes them: the
    German catalog in the spelling of Germany and Austria outside Switzerland, then the
    variety's overlays on top, the nearest last (de-DE.json, de-AT.json for German in
    Austria). Swiss: the catalog as it is."""
    texts = dict(catalogs()[lang])
    if lang == "de" and region != "CH":
        texts = {key: standard_spelling(text) for key, text in texts.items()}
    for key in reversed(overlay_chain(variety(lang, region))):
        texts.update({k: v for k, v in overlays()[key].items() if not k.startswith("_")})
    return texts


def finding_texts() -> dict[str, str]:
    """The English templates of the rule checker's messages as catalog entries."""
    return {f"finding.{key}": text for key, text in MESSAGES.items()}


def rule_texts() -> dict[str, str]:
    """The rules' titles (the "Rule" column of docs/rules.md) as catalog entries
    `rule.<ID>`, one per rule."""
    from leichtfacile.rules import RULES  # importing the package registers every rule

    return {f"rule.{rule_id}": spec.title for rule_id, spec in RULES.items()}


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
    """`t("key", name=value)` in Python and in the templates, in an interface language
    and the installation's region (`texts.region`, CH when not given), which picks the
    overlays of the language's variety and the country the texts name."""

    def __init__(self, lang: str = DEFAULT_LANG, region: str = "CH") -> None:
        all_catalogs = catalogs()
        self.lang = lang if lang in all_catalogs else DEFAULT_LANG
        self.region = region
        self._texts = variety_catalog(self.lang, region)
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
        return f"{key}.{plural_form(self.lang, n)}"

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

    def number(self, n: float) -> str:
        """A count with its thousands separated as the interface writes them, by the
        text `js.thousands` (app.js's `number` reads it too): 1,960 in English and
        French, 1'960 in German and Italian, 1.960 in the German of Germany and Austria."""
        return f"{round(n):,}".replace(",", self("js.thousands"))

    @property
    def country(self) -> str:
        """The installation's country as the texts name it after "in" (`country.<region>`:
        Switzerland, in German "der Schweiz"), for the placeholder {country}."""
        return self(f"country.{self.region}")

    @property
    def spelling(self) -> str:
        """The spelling of the installation's German variety (`spelling.<region>`: Swiss
        spelling), for the placeholder {spelling}."""
        return self(f"spelling.{self.region}")

    def language(self, lang: str, region: str | None = None) -> str:
        """The name of a document language (`lang.<code>`). German names its variety
        (`lang.de-DE`: German (Germany)) when the document's region, by default the
        installation's, or the installation's is not Swiss, so a Swiss installation
        reads "German" as before; French and Italian have one variety."""
        region = region or self.region
        key = f"lang.{lang}-{region}"
        if (region != "CH" or self.region != "CH") and self.has(key):
            return self(key)
        return self.get(f"lang.{lang}", lang)


ENGLISH = Translator(DEFAULT_LANG)
