"""Word frequencies and a German compound splitter.

Frequencies come from wordfreq (code Apache-2.0, data CC BY-SA 4.0), on the Zipf
scale: 6 is a very common word, 3 a word seen once per million words, 0 unknown.
The splitter proposes where a long compound gets its Mediopunkt (rule LEX-01):
Prämienverbilligung -> Prämien·verbilligung. It only splits where both parts are
known words, allowing the usual linking elements (Ergänzungs·leistungen).
"""

from __future__ import annotations

from functools import lru_cache

import wordfreq

MEDIOPUNKT = "\u00b7"
_LINKS_DE = ("", "s", "es", "n", "en", "e", "er", "ens", "ns")
_MIN_PART = 3
_MIN_ZIPF = 1.5  # parts must be known words; real heads like "verbilligung" are rare
_MIN_ZIPF_SHORT = 3.0  # parts of 3-4 letters must be common words (Amt, Tag, Geld)
# Frequent strings that are never parts of a compound: function words, prefixes and
# suffixes. Without this list "ver", "ich" or "ten" would pass the frequency test.
_NOT_PARTS = frozenset(
    [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "ein",
        "eine",
        "einer",
        "eines",
        "einem",
        "einen",
        "ich",
        "du",
        "er",
        "sie",
        "es",
        "wir",
        "ihr",
        "ihn",
        "ihm",
        "uns",
        "mich",
        "dich",
        "sich",
        "mir",
        "dir",
        "und",
        "oder",
        "aber",
        "als",
        "wie",
        "wenn",
        "dass",
        "ob",
        "weil",
        "fur",
        "für",
        "von",
        "vom",
        "zum",
        "zur",
        "mit",
        "bei",
        "nach",
        "vor",
        "aus",
        "auf",
        "an",
        "am",
        "im",
        "in",
        "um",
        "zu",
        "ab",
        "bis",
        "durch",
        "gegen",
        "ohne",
        "über",
        "unter",
        "hin",
        "her",
        "weg",
        "ver",
        "ent",
        "zer",
        "be",
        "ge",
        "miss",
        "ur",
        "un",
        "ten",
        "ung",
        "ungen",
        "heit",
        "keit",
        "keiten",
        "heiten",
        "lich",
        "lichen",
        "isch",
        "ig",
        "nis",
        "nisse",
        "tum",
        "schaft",
        "chen",
        "lein",
        "ist",
        "sind",
        "war",
        "hat",
        "kei",
        "ens",
        "ers",
        "nen",
        "sen",
        "ter",
        "ige",
        "igen",
        "ion",
        "ionen",
        "tion",
        "ität",
        "eit",
        "eiten",
        "ste",
        "sten",
        "end",
        "ende",
        "enden",
        "ner",
        "nern",
    ]
)


@lru_cache(maxsize=200_000)
def zipf(word: str, lang: str = "de") -> float:
    return wordfreq.zipf_frequency(word, lang)


def is_known(word: str, lang: str = "de", min_zipf: float = _MIN_ZIPF) -> bool:
    return zipf(word.lower(), lang) >= min_zipf


_SUFFIX_HEADS = ("lich", "keit", "heit", "schaft", "isch", "tum", "nis")


def _part_score(part: str, lang: str, *, head: bool = False) -> float | None:
    """Zipf frequency of a possible compound part, or None if it cannot be one."""
    if len(part) < _MIN_PART or part in _NOT_PARTS:
        return None
    if head and (part.startswith(_SUFFIX_HEADS) or part in ("ung", "ungs", "ungen")):
        return None
    z = zipf(part, lang)
    floor = {3: _MIN_ZIPF_SHORT, 4: _MIN_ZIPF_SHORT}.get(len(part), _MIN_ZIPF)
    return z if z >= floor else None


@lru_cache(maxsize=50_000)
def _best_split(word: str, lang: str) -> tuple[float, int, str, float] | None:
    """Best split of a lowercase word: (score, position, linking element, weakest part)."""
    best: tuple[float, int, str, float] | None = None
    for i in range(_MIN_PART, len(word) - _MIN_PART + 1):
        left, right = word[:i], word[i:]
        z_right = _part_score(right, lang, head=True)
        if z_right is None:
            continue
        for link in _LINKS_DE:
            if link and not left.endswith(link):
                continue
            stem = left[: len(left) - len(link)] if link else left
            if len(stem) < _MIN_PART:
                continue
            z_left = _part_score(stem, lang)
            if z_left is None:
                inner = _best_split(stem, lang)  # the modifier may be a compound itself
                if inner is None:
                    continue
                z_left = inner[0] - 0.5
            # Prefer frequent parts; a small bonus for a longer head keeps the
            # split at the main joint (Kranken·versicherung, not Krankenver·sicherung).
            weakest = min(z_left, z_right)
            score = weakest + 0.02 * len(right) - 0.1 * len(link)
            if best is None or score > best[0]:
                best = (score, i, link, weakest)
    return best


def _split_lower(word: str, max_letters: int, lang: str) -> list[str] | None:
    found = _best_split(word, lang)
    if found is None:
        return None
    _, pos, link, weakest = found
    # A derived word that is more frequent than its supposed parts is not a compound
    # (Informationen, Unterstützung, Schweizerische).
    if zipf(word, lang) - 0.3 > weakest:
        return None
    left, right = word[:pos], word[pos:]
    parts: list[str] = []
    if max_letters and len(left) > max_letters:
        stem = left[: len(left) - len(link)] if link else left
        sub = _split_lower(stem, max_letters, lang)
        if sub:
            sub[-1] += link  # the linking element stays with its part: Versicherungs·
            parts.extend(sub)
        else:
            parts.append(left)
    else:
        parts.append(left)
    if max_letters and len(right) > max_letters:
        parts.extend(_split_lower(right, max_letters, lang) or [right])
    else:
        parts.append(right)
    return parts


def split_compound(word: str, max_letters: int = 0, lang: str = "de") -> list[str] | None:
    """Split a compound into parts; parts longer than max_letters are split again.

    Returns None when no split into known words exists. Casing: the first part keeps
    the word's capital, later parts are lowercase, as Leichte Sprache writes them.
    """
    letters = word.replace(MEDIOPUNKT, "")
    if not letters.isalpha() or len(letters) < 2 * _MIN_PART:
        return None
    parts = _split_lower(letters.lower(), max_letters, lang)
    if not parts:
        return None
    first = letters[: len(parts[0])]
    return [first, *parts[1:]]


def with_mediopunkt(word: str, max_letters: int = 0, lang: str = "de") -> str | None:
    parts = split_compound(word, max_letters, lang)
    return MEDIOPUNKT.join(parts) if parts else None


def is_common_compound(word: str, lang: str = "de", min_zipf: float = 3.0) -> bool:
    """A compound whose parts are all common words (Kranken·kasse, Steuer·amt)."""
    parts = split_compound(word, lang=lang)
    if not parts:
        return False
    stems = [p.lower().rstrip("s") if len(p) > 4 else p.lower() for p in parts]
    return all(
        max(zipf(p.lower(), lang), zipf(s, lang)) >= min_zipf
        for p, s in zip(parts, stems, strict=True)
    )
