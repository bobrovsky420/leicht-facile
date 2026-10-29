"""Reference pairs: the manifest (data/pairs/manifest.jsonl) and the local text cache.

The repository holds only URLs and licence notes; the texts are fetched into
data.dir/cache/pairs/ (git-ignored) because the publishers do not allow reproduction
(docs/sources.md §4). Evaluation always reads the cached copy, not the live page.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from leichtfacile.config import paths
from leichtfacile.schemas import SourceDocument

log = logging.getLogger(__name__)

MANIFEST = Path("data/pairs/manifest.jsonl")
Side = Literal["standard", "easy"]


def data_dir() -> Path:
    """data.dir from the settings, without the endpoint (no key is needed for the
    dataset)."""
    return paths().dir


def cache_dir() -> Path:
    return data_dir() / "cache" / "pairs"


class Pair(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    publisher: str = ""
    canton: str = ""
    lang: Literal["de", "fr", "it"]
    region: Literal["CH", "DE", "AT"] = "CH"  # the national variety the pair is written in
    level: Literal["A2", "B1"] = "A2"
    role: Literal["dev", "eval", "example"] = "eval"
    topic: str = ""
    url_standard: str = Field(validation_alias=AliasChoices("url_standard", "standard_url"))
    url_easy: str = Field(validation_alias=AliasChoices("url_easy", "easy_url"))
    section_standard: str | None = Field(
        default=None, validation_alias=AliasChoices("section_standard", "standard_section")
    )
    section_easy: str | None = Field(
        default=None, validation_alias=AliasChoices("section_easy", "easy_section")
    )
    words_standard: int | None = Field(
        default=None, validation_alias=AliasChoices("words_standard", "standard_words")
    )
    words_easy: int | None = Field(
        default=None, validation_alias=AliasChoices("words_easy", "easy_words")
    )
    facts_estimate: int | None = None
    licence_note: str = Field(default="", validation_alias=AliasChoices("licence_note", "license"))
    notes: str = ""

    def url(self, side: Side) -> str:
        return self.url_standard if side == "standard" else self.url_easy

    def section(self, side: Side) -> str | None:
        return self.section_standard if side == "standard" else self.section_easy


def load_manifest(path: Path = MANIFEST) -> list[Pair]:
    pairs = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                pairs.append(Pair.model_validate(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"{path}:{n}: {exc}") from exc
    ids = [p.id for p in pairs]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate pair ids in {path}: {sorted(duplicates)}")
    return pairs


def select(
    pairs: Iterable[Pair],
    *,
    role: str | None = None,
    lang: str | None = None,
    ids: Iterable[str] | None = None,
) -> list[Pair]:
    wanted = set(ids or [])
    out = []
    for p in pairs:
        if wanted and p.id not in wanted:
            continue
        if role not in (None, "all") and p.role != role:
            continue
        if lang and p.lang != lang:
            continue
        out.append(p)
    return out


def cached_path(pair_id: str, side: Side, root: Path | None = None) -> Path:
    return (root or cache_dir()) / f"{pair_id}.{side}.json"


@dataclass
class FetchReport:
    fetched: list[str]
    cached: list[str]
    failed: dict[str, str]


def fetch_pairs(
    pairs: Iterable[Pair], *, refresh: bool = False, root: Path | None = None, delay_s: float = 1.0
) -> FetchReport:
    from leichtfacile import ingest
    from leichtfacile.ingest.errors import IngestError

    root = root or cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    report = FetchReport([], [], {})
    for pair in pairs:
        for side in ("standard", "easy"):
            key = f"{pair.id}.{side}"
            path = cached_path(pair.id, side, root)
            if path.exists() and not refresh:
                report.cached.append(key)
                continue
            try:
                doc = ingest.ingest_url(
                    pair.url(side), lang=pair.lang, doc_id=key, license_note=pair.licence_note
                )
                section = pair.section(side)
                if section:
                    doc = ingest.select_section(doc, section)
            except IngestError as exc:
                report.failed[key] = str(exc)
                log.warning("fetch %s failed: %s", key, exc)
            else:
                path.write_text(doc.model_dump_json(indent=1), encoding="utf-8")
                report.fetched.append(key)
            time.sleep(delay_s)
    return report


def load_side(pair: Pair, side: Side, root: Path | None = None) -> SourceDocument:
    path = cached_path(pair.id, side, root)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing: run `python -m leichtfacile eval fetch` first")
    doc = SourceDocument.model_validate_json(path.read_text(encoding="utf-8"))
    # The cached text carries no region; the pair says which variety it is written in.
    return doc.model_copy(update={"region": pair.region})


def load_pair(pair: Pair, root: Path | None = None) -> tuple[SourceDocument, SourceDocument]:
    return load_side(pair, "standard", root), load_side(pair, "easy", root)
