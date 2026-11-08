"""Record the runs the web app replays for the sample letters (samples/README.md,
src/leichtfacile/llm/replay.py), and check them.

Usage: uv run python scripts/record_samples.py [--preset publicai-apertus]
       [--only <letter> ...] [--attempts 6] [--parallel 3] [--allow-problems]
       [--work data/cache/record]
       uv run python scripts/record_samples.py --check

Each letter runs as the New draft form sends it unchanged (`example_submission` and
`create_job` in src/leichtfacile/web/jobs.py), with a `Recorder` as the response cache, in
an installation of its own in the work folder (git-ignored under data/cache/): the
shipped defaults and presets, no leichtfacile.toml, .env or LEICHTFACILE_ variable of the
checkout, only the preset's key (from the environment, else from the repository's .env),
so that the prompts are those of a fresh installation. A run has no time budget: one
cut short would replay past its end. `--parallel` attempts run at a time until one
reaches review clean (no error, nothing that blocks publication, every fact kept, no
stage skipped), at most `--attempts` in all. The clean run with the fewest warnings that
replays without an endpoint is written to
samples/leichtfacile_samples/recordings/<preset>/<letter>.json. A letter without one keeps
the recording it has; --allow-problems takes the run with the fewest problems instead.
Every attempt stays in the work folder's store (data/record.sqlite).

--check replays every recording without an endpoint (`check_recording` in
src/leichtfacile/examples.py, as .github/workflows/samples.yml does before it publishes the
package) and names those a changed prompt has made stale.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from dotenv import dotenv_values
from leichtfacile_samples import RECORDINGS

from leichtfacile import __version__, config
from leichtfacile.config import LETTERS_DIR
from leichtfacile.examples import check_recording, example_sources, settings_for
from leichtfacile.llm.client import LLMClient
from leichtfacile.llm.replay import Recorder, Recording, read_recording, write_recording
from leichtfacile.pipeline.orchestrator import Orchestrator
from leichtfacile.schemas import PipelineSummary
from leichtfacile.store import Store
from leichtfacile.web.jobs import create_job, example_submission

if TYPE_CHECKING:
    from leichtfacile.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRESET = "publicai-apertus"  # the shipped default and the Apertus demo's

log = logging.getLogger("record_samples")


def isolate(work: Path, preset: str | None) -> None:
    """This process's settings as those of a fresh installation in `work`: its own
    config file naming the preset and a data folder there, none of the checkout's files
    or variables, and the preset's key alone."""
    key = None
    if preset is not None:
        provider = config.PRESETS[preset]["provider"]
        name = config.PROVIDERS[provider]["api_key_env"]
        value = os.environ.get(name) or dotenv_values(ROOT / ".env").get(name)
        key = (name, value) if value else None
    for name in list(os.environ):
        if name.upper().startswith(config.ENV_PREFIX) or name.endswith(("_API_KEY", "_TOKEN")):
            del os.environ[name]
    work.mkdir(parents=True, exist_ok=True)
    lines = [f'[llm]\npreset = "{preset}"\n'] if preset else []
    (work / "config.toml").write_text("".join(lines) + '[data]\ndir = "data"\n', encoding="utf-8")
    os.environ["LEICHTFACILE_CONFIG"] = str(work / "config.toml")
    config.PROJECT_FILE = work / "leichtfacile.toml"
    config.LOCAL_ENV_FILE = work / ".env"
    if key:
        os.environ[key[0]] = key[1]
    config.use_overrides({})


@dataclass
class Attempt:
    """One run of a letter: once it reached review, its recording with the answers and
    what the drafts list shows."""

    recording: Recording | None = None
    answers: list[dict[str, Any]] = field(default_factory=list)
    problems: tuple[int, ...] = ()  # errors, blocking, facts missing, stages skipped
    warnings: int = 0

    @property
    def clean(self) -> bool:
        return self.recording is not None and not any(self.problems)


def attempt(store: Store, settings: Settings, preset: str, example: dict[str, str], n: int):
    """Run the letter as the New draft form sends it, with a `Recorder` as the cache."""
    name = example["id"]
    recorder = Recorder()
    llm = LLMClient(settings, cache=recorder, usage_sink=recorder.observe)
    print(f"{name} #{n}: running")
    try:
        job = create_job(store, settings, example_submission(example))
        Orchestrator(store, llm, settings).run(job.id)
    except Exception:  # one attempt failing must not end the others
        log.exception("%s #%d failed", name, n)
        return Attempt()
    done = store.get_job(job.id)
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    if done is None or done.status != "needs_review" or done.counts is None or summary is None:
        print(f"{name} #{n}: no review ({done.error if done else 'gone'})")
        return Attempt()
    c = done.counts
    problems = (c.errors, c.blocking or 0, c.facts_total - c.facts_present, len(summary.notes))
    seconds = sum(u.latency_ms for u in done.usage) / 1000
    print(
        f"{name} #{n}: job {job.id}, {c.errors} errors, {c.blocking or 0} blocking, "
        f"{c.facts_present}/{c.facts_total} facts, {c.warnings} warnings, "
        f"{len(done.usage)} calls, {seconds:.0f} s"
    )
    models = {"writer": summary.writer_model, "judge": summary.judge_model or ""}
    if summary.understand_model:
        models["understand"] = summary.understand_model
    url = urlsplit(settings.llm.url)
    recording = Recording(
        letter=name,
        preset=preset,
        models=models,
        recorded_at=datetime.now(UTC),
        version=__version__,
        endpoint=f"{url.scheme}://{url.hostname}",
        seconds=seconds,
        calls=len(done.usage),
        result={
            "job": job.id,
            "final_version": summary.final_version,
            "errors": c.errors,
            "warnings": c.warnings,
            "blocking": c.blocking or 0,
            "facts_present": c.facts_present,
            "facts_total": c.facts_total,
        },
    )
    return Attempt(recording, recorder.answers, problems, c.warnings)


def keep(best: list[Attempt], settings: Settings) -> Path | None:
    """The first of the runs, best first, that replays without an endpoint, written to
    the recordings; None when none does."""
    with tempfile.TemporaryDirectory(prefix="leichtfacile-record-") as tmp:
        for run in best:
            if run.recording is None:
                continue
            trial = write_recording(Path(tmp), run.recording, run.answers)
            problem = check_recording(trial, settings)
            if problem is None:
                return write_recording(RECORDINGS, run.recording, run.answers)
            print(f"{run.recording.letter}: job {run.recording.result['job']} not kept: {problem}")
    return None


def record(args: argparse.Namespace) -> int:
    loaded = config.load(strict=False, preset=args.preset)
    if loaded.problems:
        sys.exit(f"the preset {args.preset} is not ready: " + "; ".join(loaded.problems))
    # No time budget: a run cut short would replay past its end.
    jobs = loaded.settings.jobs.model_copy(update={"time_budget_s": 0.0})
    settings = loaded.settings.model_copy(update={"jobs": jobs})
    store = Store(settings.data.dir / "record.sqlite")
    letters = [e for e in example_sources(LETTERS_DIR) if not args.only or e["id"] in args.only]
    missing = 0
    with ThreadPoolExecutor(args.parallel) as pool:
        for example in letters:
            run = partial(attempt, store, settings_for(settings, example), args.preset, example)
            runs: list[Attempt] = []
            while len(runs) < args.attempts and not any(r.clean for r in runs):
                batch = range(len(runs) + 1, min(len(runs) + args.parallel, args.attempts) + 1)
                runs += pool.map(run, batch)
            usable = [r for r in runs if r.clean or (args.allow_problems and r.recording)]
            written = keep(sorted(usable, key=lambda r: (r.problems, r.warnings)), settings)
            if written is None:
                missing += 1
                print(
                    f"{example['id']}: not recorded ({len(runs)} runs, none clean and replayable)"
                )
            else:
                print(f"{example['id']}: written to {written.relative_to(ROOT)}")
    store.close()
    return 1 if missing else 0


def check() -> int:
    stale = 0
    paths = sorted(RECORDINGS.glob("*/*.json"))
    for path in paths:
        recording, _ = read_recording(path)
        settings = config.load(strict=False, preset=recording.preset).settings
        problem = check_recording(path, settings)
        print(f"{recording.path}: {problem or 'replays'}")
        stale += problem is not None
    print(f"{len(paths) - stale} of {len(paths)} recordings replay")
    return 1 if stale else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    parser.add_argument("--only", nargs="+", metavar="LETTER", help="letters by file name")
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--allow-problems", action="store_true")
    parser.add_argument("--work", type=Path, default=Path("data/cache/record"))
    parser.add_argument("--check", action="store_true", help="replay every recording")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    isolate((ROOT / args.work).resolve(), None if args.check else args.preset)
    return check() if args.check else record(args)


if __name__ == "__main__":
    raise SystemExit(main())
