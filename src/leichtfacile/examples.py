"""The example letters in src/leichtfacile/letters/, shipped with the package: offered as
one-click fills of the New draft form and of the empty drafts list, and used by the
tests and the smoke run (docs/quickstart.md). data.examples_dir points at another folder
of letters.

The JSON file next to a letter holds its job settings: the decision mode's (`mode`,
`addressee`, `notice`) and the region the letter is written for (`region`: CH, DE or
AT). An installation offers the letters of its variety (`texts.region`): the German
letters of its country and the French and Italian ones, which are Swiss for every
installation. A letter whose file names no region is offered everywhere.

Only team-written or article-5 texts are used as examples (docs/sources.md §4).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from leichtfacile.config import paths
from leichtfacile.schemas import JobConfig
from leichtfacile.varieties import region_for

# The settings of a letter that go with it into the form and the page.
FIELDS = ("mode", "addressee", "notice", "region")


def examples_dir() -> Path:
    """data.examples_dir from the settings, without the endpoint (no key is needed to
    read the examples). The web app passes `settings.data.examples_dir`."""
    return paths().examples_dir


def example_sources(folder: Path | None = None, region: str | None = None) -> list[dict[str, str]]:
    """The team-written example texts offered in the New draft form: id, title, text and
    the detected language (`lang`, "" when unclear), plus the job settings of the
    decision mode (`mode`, `addressee`, `notice`) and the letter's `region` from the
    JSON file next to a letter, when it has one (`example_config`). With `region`, the
    installation's `texts.region`, only the letters it offers: those written for the
    region their language has there (`varieties.region_for`), and those naming none."""
    folder = folder or examples_dir()
    out = []
    for path in sorted(folder.glob("*.txt")) + sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        settings = example_config(path)
        lang = language_of(text)
        written_for = settings.get("region")
        if region is not None and written_for and written_for != region_for(lang, region):
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else path.stem
        fields = {k: settings[k] for k in FIELDS if settings.get(k)}
        out.append({"id": path.stem, "title": title, "text": text, "lang": lang, **fields})
    return out


@lru_cache(maxsize=64)
def language_of(text: str) -> str:
    """The language of a letter, detected once per text; "" when the evidence is unclear."""
    from leichtfacile.ingest.detect import detect_language

    return detect_language(text)[0] or ""


def example_config(path: Path) -> dict[str, Any]:
    """Job settings for one example letter from the JSON file next to it, if any:
    `entscheid.txt` with `entscheid.json` holding `{"mode": "decision", "addressee": ...}`.
    Only JobConfig fields are allowed."""
    sidecar = path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    unknown = set(data) - set(JobConfig.model_fields)
    if unknown:
        raise ValueError(f"{sidecar.name}: not job settings: {', '.join(sorted(unknown))}")
    return data
