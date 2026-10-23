"""The example letters in data/examples/sources/: offered as one-click fills of the New
draft form and of the empty drafts list, and used by the tests and `make smoke`.

Only team-written or article-5 texts are used as sources (docs/sources.md §4).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from leichtfacile.config import Paths
from leichtfacile.schemas import JobConfig


def examples_dir() -> Path:
    """EXAMPLES_DIR from the environment or .env, without the model settings (no key
    is needed to read the examples). The web app passes `Settings.examples_dir`."""
    return Paths().examples_dir


def example_sources(folder: Path | None = None) -> list[dict[str, str]]:
    """The team-written example texts offered in the New draft form: id, title and text,
    plus the job settings of the decision mode (`mode`, `addressee`, `notice`) from the
    JSON file next to a source, when it has one (`example_config`)."""
    folder = (folder or examples_dir()) / "sources"
    out = []
    for path in sorted(folder.glob("*.txt")) + sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else path.stem
        settings = example_config(path)
        fields = {k: settings[k] for k in ("mode", "addressee", "notice") if settings.get(k)}
        out.append({"id": path.stem, "title": title, "text": text, **fields})
    return out


def example_config(path: Path) -> dict[str, Any]:
    """Job settings for one example source from the JSON file next to it, if any:
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
