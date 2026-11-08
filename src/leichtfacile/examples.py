"""The example letters of the package leichtfacile-samples (samples/README.md), a
dependency of the app: offered as one-click fills of the New draft form and of the
empty drafts list, and used by the tests and the smoke run (docs/quickstart.md). Their
recorded runs answer them in the web app (llm/replay.py). data.examples_dir points at
another folder of letters.

The JSON file next to a letter holds its job settings: the decision mode's (`mode`,
`addressee`, `notice`) and the region the letter is written for (`region`: CH, DE or
AT), and a short `description` of the letter in its own language, which the empty
drafts list shows under the title. An installation offers the letters of its variety
(`texts.region`): the German letters of its country and the French and Italian ones,
which are Swiss for every installation. A letter whose file names no region is offered
everywhere.

Only team-written or article-5 texts are used as examples (docs/sources.md §4).
"""

from __future__ import annotations

import json
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from leichtfacile.config import LETTERS_DIR, paths
from leichtfacile.schemas import JobConfig
from leichtfacile.varieties import region_for

if TYPE_CHECKING:
    from leichtfacile.config import Settings

# The settings of a letter that go with it into the form and the page.
FIELDS = ("mode", "addressee", "notice", "region", "sender", "address")
# What the file may hold besides job settings: the letter's short description.
PRESENTATION = ("description",)


def examples_dir() -> Path:
    """data.examples_dir from the settings, without the endpoint (no key is needed to
    read the examples). The web app passes `settings.data.examples_dir`."""
    return paths().examples_dir


def example_sources(folder: Path | None = None, region: str | None = None) -> list[dict[str, str]]:
    """The team-written example texts offered in the New draft form: id, title, text,
    the detected language (`lang`, "" when unclear) and the `description` ("" without
    one), plus the job settings of the decision mode (`mode`, `addressee`, `notice`) and
    the letter's `region` from the JSON file next to a letter, when it has one. With
    `region`, the installation's `texts.region`, only the letters it offers: those
    written for the region their language has there (`varieties.region_for`), and those
    naming none."""
    folder = folder or examples_dir()
    out = []
    for path in sorted(folder.glob("*.txt")) + sorted(folder.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        settings = _sidecar(path)
        lang = language_of(text)
        written_for = settings.get("region")
        if region is not None and written_for and written_for != region_for(lang, region):
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else path.stem
        fields = {k: settings[k] for k in FIELDS if settings.get(k)}
        description = str(settings.get("description") or "").strip()
        out.append(
            {
                "id": path.stem,
                "title": title,
                "text": text,
                "lang": lang,
                "description": description,
                **fields,
            }
        )
    return out


@lru_cache(maxsize=64)
def language_of(text: str) -> str:
    """The language of a letter, detected once per text; "" when the evidence is unclear."""
    from leichtfacile.ingest.detect import detect_language

    return detect_language(text)[0] or ""


def example_config(path: Path) -> dict[str, Any]:
    """Job settings for one example letter from the JSON file next to it, if any:
    `entscheid.txt` with `entscheid.json` holding `{"mode": "decision", "addressee": ...}`.
    The letter's description is left out: it is not a job setting."""
    return {k: v for k, v in _sidecar(path).items() if k not in PRESENTATION}


def settings_for(settings: Settings, example: dict[str, str]) -> Settings:
    """The settings of an installation that offers the letter: `texts.region` is the
    letter's region (CH for a letter without one)."""
    texts = settings.texts.model_copy(update={"region": example.get("region") or "CH"})
    return settings.model_copy(update={"texts": texts})


def check_recording(path: Path, settings: Settings, folder: Path | None = None) -> str | None:
    """Replay a recorded run (llm/replay.py) without an endpoint: the letter of `folder`
    (the package's letters by default) as the New draft form sends it, through the
    pipeline on `settings`, those of the preset it was recorded on in an installation
    with the defaults. None when every call was answered from the recording and the job
    reached review; else what went wrong: a prompt that changed since the recording
    went to the endpoint, which refuses it."""
    import httpx

    from leichtfacile.llm.client import LLMClient
    from leichtfacile.llm.replay import Replay, read_recording
    from leichtfacile.pipeline.orchestrator import Orchestrator
    from leichtfacile.store import Store
    from leichtfacile.web.jobs import create_job, example_submission

    recording, answers = read_recording(path)
    found = [e for e in example_sources(folder or LETTERS_DIR) if e["id"] == recording.letter]
    if not found:
        return f"no letter {recording.letter}"
    asked: list[str] = []  # the models of the calls the recording could not answer

    def refuse(request: httpx.Request) -> httpx.Response:
        asked.append(json.loads(request.content or b"{}").get("model", request.url.path))
        return httpx.Response(400, json={"error": {"message": "not recorded"}})

    settings = settings_for(settings, found[0])
    endpoint = httpx.Client(transport=httpx.MockTransport(refuse))
    llm = LLMClient(settings, http_client=endpoint, replay=Replay([(recording, answers)]))
    with tempfile.TemporaryDirectory(prefix="leichtfacile-replay-") as tmp:
        store = Store(Path(tmp) / "check.sqlite")
        try:
            job = create_job(store, settings, example_submission(found[0]))
            Orchestrator(store, llm, settings).run(job.id)
            ended = store.get_job(job.id)
        finally:
            store.close()
            endpoint.close()
    if asked:
        return f"{len(asked)} calls not recorded, the first to {asked[0]}"
    if ended is None or ended.status != "needs_review":
        return f"the job ended {ended.status if ended else 'gone'}: {ended.error if ended else ''}"
    return None


def _sidecar(path: Path) -> dict[str, Any]:
    """The JSON file next to a letter, checked: JobConfig fields and the presentation
    keys (`PRESENTATION`), nothing else; empty without the file."""
    sidecar = path.with_suffix(".json")
    if not sidecar.is_file():
        return {}
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    unknown = set(data) - set(JobConfig.model_fields) - set(PRESENTATION)
    if unknown:
        raise ValueError(f"{sidecar.name}: not job settings: {', '.join(sorted(unknown))}")
    return data
