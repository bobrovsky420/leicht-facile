"""The screenshots of the user's guide (docs/user-guide.md) and of its pages on the site.

Usage: uv run python scripts/guide_screenshots.py [--work data/cache/guide]
       [--preset publicai-apertus] [--langs en de] [--out docs/images/guide]
       [--site ../leicht-facile-web/site] [--redo]

Writes docs/images/guide/<lang>/<name>.webp (lossless), 1280 px wide and at most 820 high
(an empty strip at the bottom is trimmed), one set per interface language, and the same
pictures into the site's images/guide (--site; by default the sibling checkout of the
leicht-facile-web repository when it exists, since 2 November 2026). The app runs
from a work folder of its own (git-ignored under data/cache/): its own config file and
data, no leichtfacile.toml and no key but the preset's, so the pictures show the shipped
presets and nothing of this checkout. Two servers run, one on an
empty store (the start page before the first draft) and one with the guide's drafts.

The first run makes the drafts with a live model: the German premium reduction letter and
the school's camp letter, a few minutes and a few cents on Public AI. The preset's key
comes from the environment or from .env in the repository. Later runs reuse the drafts
and call no model; --redo makes them again. The running job on the progress picture is a
copy of the first draft as it stood when the first repair round began, made in the store
and deleted again, so no model call is needed for it either.

Headless Edge takes the pictures through the DevTools protocol (Playwright is not needed):
EDGE below, or --browser for another Chromium.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from websockets.sync.client import connect

from leichtfacile.examples import example_sources
from leichtfacile.schemas import Draft, PipelineSummary, ReviewState
from leichtfacile.store import Store

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / "leicht-facile-web" / "site"  # the project's page, a sibling checkout
PRESETS = ROOT / "src" / "leichtfacile" / "presets" / "presets.toml"
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
WIDTH, HEIGHT = 1280, 820
APP_PORT, EMPTY_PORT, DEBUG_PORT = 8791, 8792, 9339
LETTER = "praemienverbilligung-brief"  # the guide's letter, followed from start to export
SECOND = "klassenlager-elternbrief"  # a second draft, so the list is a list
DEMO_ID = "guide0running"  # the running copy on the progress picture
LOCAL_PROVIDERS = ("local", "ollama", "vllm")  # the shipped providers on this computer
MARGIN = 24  # px of page background kept below the content when a picture is trimmed
APPROVED = 6  # the first blocks of the guide's letter, approved, so the list shows progress

# A text with findings for the Check my text picture: one long sentence with a passive and
# a hard word, then two easy ones. The phone number follows data/examples/README.md.
CHECK_TEXT = (
    "Prämienverbilligung 2027\n\n"
    "Der Antrag ist vollständig ausgefüllt und unterzeichnet bis spätestens 31. März 2027 "
    "bei der Sozialversicherungsstelle einzureichen, wobei verspätet eingereichte Anträge "
    "nicht berücksichtigt werden.\n\n"
    "Haben Sie Fragen?\nRufen Sie uns an: 022 123 45 67.\n"
)


def free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def key_variable(preset: str) -> str:
    """The environment variable of the preset's provider key, from the shipped presets."""
    data = tomllib.loads(PRESETS.read_text(encoding="utf-8"))
    provider = data["presets"][preset]["provider"]
    return data["providers"][provider]["api_key_env"]


def dotenv(name: str) -> str | None:
    """`name` from the environment, else from the repository's .env."""
    if value := os.environ.get(name):
        return value
    path = ROOT / ".env"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name:
            return value.strip().strip("\"'")
    return None


def server_env(work: Path, preset: str) -> dict[str, str]:
    """The environment without this machine's keys and LEICHTFACILE_ settings, with the
    work folder's config file and the preset's key alone."""
    secrets = ("_API_KEY", "_TOKEN")
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("LEICHTFACILE_") and not k.endswith(secrets)
    }
    config = work / "config.toml"
    # The model servers of this machine stay out of the pictures: their providers point at a
    # closed port, so the AI model page shows them as not running.
    closed = "".join(
        f'[providers.{name}]\nurl = "http://127.0.0.1:9/v1"\n' for name in LOCAL_PROVIDERS
    )
    config.write_text(f'[llm]\npreset = "{preset}"\ncache = true\n{closed}', encoding="utf-8")
    env["LEICHTFACILE_CONFIG"] = str(config)
    env["LEICHTFACILE_SERVER__UI_LANG"] = "en"
    name = key_variable(preset)
    if key := dotenv(name):
        env[name] = key
    return env


@contextmanager
def server(work: Path, data: Path, port: int, env: dict[str, str]) -> Iterator[str]:
    """`leichtfacile serve` on `data`, started from the work folder; yields its address."""
    if not free(port):
        sys.exit(f"port {port} is in use: stop what runs there first")
    log = (work / f"serve-{port}.log").open("w", encoding="utf-8")
    cmd = [sys.executable, "-m", "leichtfacile", "serve", "--port", str(port), "--no-browser"]
    proc = subprocess.Popen(
        cmd, cwd=work, env={**env, "LEICHTFACILE_DATA__DIR": str(data)}, stdout=log, stderr=log
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(240):
            if proc.poll() is not None:
                sys.exit(f"the server on port {port} stopped: see {log.name} in {work}")
            try:
                if httpx.get(f"{base}/healthz", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            sys.exit(f"the server on port {port} did not start: see {log.name} in {work}")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        log.close()


# -- the drafts --------------------------------------------------------------------------


def example(example_id: str) -> dict[str, str]:
    return next(e for e in example_sources() if e["id"] == example_id)


def find_job(store: Store, title: str) -> str | None:
    jobs = store.list_jobs(limit=100)
    return next((j.id for j in jobs if j.title == title and j.status != "failed"), None)


def make_job(base: str, store: Store, example_id: str) -> str:
    """The draft of an example letter, made by the live model; waits until it is ready."""
    e = example(example_id)
    fields: dict[str, str] = {
        k: e[k] for k in ("mode", "addressee", "notice", "sender", "address") if k in e
    }
    form: dict[str, Any] = {
        "text": e["text"],
        "lang": e["lang"],
        "level": "A2",
        "condition": "P2",
        "title": e["title"],
        **fields,
    }
    r = httpx.post(f"{base}/api/v1/jobs", files={k: (None, v) for k, v in form.items()}, timeout=60)
    r.raise_for_status()
    job_id = r.json()["id"]
    print(f"{e['title']}: job {job_id}, waiting for the model")
    last = None
    deadline = time.monotonic() + 45 * 60
    while time.monotonic() < deadline:
        job = store.get_job(job_id)
        if job is None:
            sys.exit(f"the job {job_id} is gone")
        if job.status in ("needs_review", "done"):
            print(f"  ready after {job.stage or 'the last stage'}")
            return job_id
        if job.status == "failed":
            sys.exit(f"the job {job_id} failed: {job.error}")
        if job.stage != last:
            print(f"  {job.status}: {job.stage or '-'}")
            last = job.stage
        time.sleep(3)
    sys.exit(f"the job {job_id} took longer than 45 minutes")


def approve_first(base: str, store: Store, job_id: str, n: int) -> None:
    """Approve the first `n` blocks of the final version, as a reviewer who has begun."""
    summary = store.get_artifact(job_id, "summary", PipelineSummary)
    if summary is None:
        sys.exit(f"the job {job_id} has no summary")
    version = summary.final_version
    draft = store.get_artifact(job_id, "draft", Draft, version=version)
    if draft is None:
        sys.exit(f"the job {job_id} has no draft {version}")
    decisions = [{"block_id": b.id, "decision": "approved"} for b in draft.blocks[:n]]
    body = {"draft_version": version, "decisions": decisions}
    httpx.post(f"{base}/api/v1/jobs/{job_id}/review", json=body, timeout=30).raise_for_status()


def drop_demo(db: Path) -> None:
    with sqlite3.connect(db) as conn:
        for table in ("llm_calls", "artifacts"):
            conn.execute(f"DELETE FROM {table} WHERE job_id = ?", (DEMO_ID,))
        conn.execute("DELETE FROM jobs WHERE id = ?", (DEMO_ID,))


def make_demo(db: Path, job_id: str) -> None:
    """A copy of the job as it stood when the first repair round began: the fact sheet and
    version 1 with its check and judgement, the calls made until then, status running.
    The worker takes only queued jobs, so it never touches the copy; drop_demo removes it
    before the server stops (a server start would queue it again)."""
    with sqlite3.connect(db) as conn:
        first_repair = conn.execute(
            "SELECT min(id) FROM llm_calls WHERE job_id = ? AND stage LIKE 'repair%'", (job_id,)
        ).fetchone()[0]
        calls = "job_id = ?" + (" AND id < ?" if first_repair else "")
        params = (job_id, first_repair) if first_repair else (job_id,)
        seconds = conn.execute(
            f"SELECT coalesce(sum(latency_ms), 0) / 1000.0 FROM llm_calls WHERE {calls}", params
        ).fetchone()[0]
        now = datetime.now(UTC)
        conn.execute(
            "INSERT INTO jobs (id, status, stage, title, created_at, updated_at, config, counts) "
            "SELECT ?, 'running', 'repair 1', title, ?, ?, config, counts FROM jobs WHERE id = ?",
            (DEMO_ID, (now - timedelta(seconds=seconds + 8)).isoformat(), now.isoformat(), job_id),
        )
        conn.execute(
            "INSERT INTO artifacts (job_id, name, version, data, created_at) "
            "SELECT ?, name, version, data, created_at FROM artifacts WHERE job_id = ? "
            "AND (name IN ('source', 'factsheet') OR (version = 1 AND name IN "
            "('draft', 'rules', 'judge')))",
            (DEMO_ID, job_id),
        )
        conn.execute(
            "INSERT INTO llm_calls (job_id, stage, model, tokens_in, tokens_out, latency_ms, "
            f"cached, at, cache_key) SELECT ?, stage, model, tokens_in, tokens_out, latency_ms, "
            f"cached, at, cache_key FROM llm_calls WHERE {calls} ORDER BY id",
            (DEMO_ID, *params),
        )


# -- the browser -------------------------------------------------------------------------


# The state of the app bar's model dot (app.js): "" until /readyz answers, "none" on a page
# without the app bar.
READY = """(() => {
  const dot = document.getElementById('endpoint-status');
  return dot ? dot.dataset.state || '' : 'none';
})()"""


class Browser:
    """One headless page, driven through the DevTools protocol."""

    def __init__(self, ws) -> None:
        self.ws = ws
        self.n = 0
        self.call("Page.enable")
        self.call(
            "Emulation.setDeviceMetricsOverride",
            width=WIDTH,
            height=HEIGHT,
            deviceScaleFactor=1,
            mobile=False,
        )
        self.call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "light"}],
        )

    def call(self, method: str, **params: object) -> dict:
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expression: str) -> object:
        result = self.call(
            "Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True
        )
        if "exceptionDetails" in result:
            raise RuntimeError(f"{expression[:60]}: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    def settle(self, seconds: float = 1.5) -> None:
        for _ in range(100):
            if self.js("document.readyState") == "complete":
                break
            time.sleep(0.1)
        self.js("document.fonts.ready.then(() => true)")
        time.sleep(seconds)  # the model dot asks /readyz, the page scrolls smoothly

    def go(self, url: str, seconds: float = 1.5) -> None:
        self.call("Page.navigate", url=url)
        time.sleep(0.3)
        self.settle(seconds)
        # the app bar's model dot stays grey until /readyz has answered: wait for its colour
        for _ in range(100):
            if self.js(READY) in ("none", "ok", "warn", "bad"):
                break
            time.sleep(0.1)

    def shoot(self, path: Path) -> None:
        data = self.call("Page.captureScreenshot", format="png")  # the viewport
        path.parent.mkdir(parents=True, exist_ok=True)
        image = trim(Image.open(io.BytesIO(base64.b64decode(data["data"]))).convert("RGB"))
        # lossless WebP: every pixel as captured, at about 40 percent of a PNG's bytes (a
        # 256-colour PNG is as small, but lost the green model dot or tinted flat areas)
        image.save(path, lossless=True, method=6)
        print(f"  {path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path}")


def trim(image: Image.Image) -> Image.Image:
    """Without the empty page background below the content (the start page, a short list),
    keeping MARGIN of it; a picture that is full to the bottom stays as it is."""
    background = image.getpixel((image.width - 1, image.height - 1))
    rows = image.height
    while rows > 0:
        line = image.crop((0, rows - 1, image.width, rows))
        if line.getcolors(1) is None or line.getpixel((0, 0)) != background:
            break  # more than one colour, or another one: content
        rows -= 1
    if image.height - rows <= 2 * MARGIN:
        return image
    return image.crop((0, 0, image.width, rows + MARGIN))


@contextmanager
def browser(exe: Path) -> Iterator[Browser]:
    if not free(DEBUG_PORT):
        sys.exit(f"port {DEBUG_PORT} is in use: close the browser that holds it")
    # Edge's helper processes may hold the profile a moment after it closed.
    with tempfile.TemporaryDirectory(
        prefix="lf-guide-edge-", ignore_cleanup_errors=True
    ) as profile:
        proc = subprocess.Popen(
            [
                str(exe),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile}",
                f"--remote-debugging-port={DEBUG_PORT}",
                f"--window-size={WIDTH},{HEIGHT}",
                "about:blank",
            ]
        )
        try:
            for _ in range(100):
                try:
                    pages = httpx.get(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2).json()
                    page = next(p for p in pages if p.get("type") == "page")
                    break
                except (httpx.HTTPError, StopIteration, ValueError):
                    time.sleep(0.2)
            else:
                sys.exit("the browser did not open its debugging port")
            with connect(page["webSocketDebuggerUrl"], max_size=None, open_timeout=30) as ws:
                yield Browser(ws)
        finally:
            # Ending the launcher leaves Edge's own processes running: close the browser
            # through its own socket and wait until the port is free again.
            with suppress(Exception):
                version = httpx.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=2)
                with connect(version.json()["webSocketDebuggerUrl"]) as ws:
                    ws.send(json.dumps({"id": 1, "method": "Browser.close"}))
            for _ in range(50):
                if free(DEBUG_PORT):
                    break
                time.sleep(0.2)
            proc.terminate()
            proc.wait(timeout=30)


# -- the pictures ------------------------------------------------------------------------


def pictures(app: str, empty: str, job_id: str) -> dict[str, Callable[[Browser], None]]:
    """Each picture's name and how to reach its state, in the guide's order."""

    def review(b: Browser) -> None:
        b.go(f"{app}/jobs/{job_id}")
        b.js("""(() => {
          const b = document.querySelector('.block.has-issues.sev-error:not(.decided)')
            || document.querySelector('.block.has-issues:not(.decided)');
          b.click();
          b.scrollIntoView({block: 'center'});
        })()""")
        b.settle(1.0)

    def facts(b: Browser) -> None:
        b.go(f"{app}/jobs/{job_id}")
        b.js("""(() => {
          const f = [...document.querySelectorAll('.fact.fact-present')]
            .find((f) => f.dataset.factSegments) || document.querySelector('.fact');
          f.click();
        })()""")
        b.settle(1.2)

    def more(b: Browser) -> None:
        b.go(f"{app}/jobs/{job_id}")
        b.js("document.getElementById('tab-more').click()")
        b.settle(0.5)

    def reader(b: Browser) -> None:
        b.go(f"{app}/jobs/{job_id}")
        b.js("document.querySelector('.view-opt[data-view=reader]').click()")
        b.settle(3.0)  # the frame loads the reader page

    def check(b: Browser) -> None:
        b.go(f"{app}/check")
        b.js(f"""(() => {{
          document.getElementById('text').value = {json.dumps(CHECK_TEXT)};
          document.getElementById('lang').value = 'de';
          document.getElementById('check-form').submit();
        }})()""")
        time.sleep(0.5)
        b.settle(0.5)
        b.js("document.getElementById('results').scrollIntoView({block: 'start'})")
        b.settle(0.5)

    return {
        "01-start": lambda b: b.go(f"{empty}/"),
        "02-new-draft": lambda b: b.go(f"{app}/new?example={LETTER}"),
        "03-progress": lambda b: b.go(f"{app}/jobs/{DEMO_ID}"),
        "04-drafts": lambda b: b.go(f"{app}/"),
        "05-review": review,
        "06-facts": facts,
        "07-more": more,
        "08-reader": reader,
        "09-check": check,
        "10-model": lambda b: b.go(f"{app}/model", 2.5),
    }


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", type=Path, default=ROOT / "data" / "cache" / "guide")
    ap.add_argument("--preset", default="publicai-apertus")
    ap.add_argument("--langs", nargs="+", default=["en", "de"])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "images" / "guide")
    ap.add_argument(
        "--site",
        type=Path,
        default=SITE if SITE.is_dir() else None,
        help="the site's folder in the leicht-facile-web checkout: the pictures go into its "
        "images/guide as well (../leicht-facile-web/site when it exists)",
    )
    ap.add_argument("--only", nargs="+", help="these pictures alone, by name (05-review)")
    ap.add_argument("--redo", action="store_true", help="make the drafts again")
    ap.add_argument("--browser", type=Path, default=EDGE)
    args = ap.parse_args()

    work = args.work.resolve()
    data, blank = work / "data", work / "empty"
    data.mkdir(parents=True, exist_ok=True)
    blank.mkdir(parents=True, exist_ok=True)
    db = data / "leichtfacile.sqlite"
    env = server_env(work, args.preset)
    if db.exists():
        drop_demo(db)
    store = Store(db)
    letter, second = example(LETTER)["title"], example(SECOND)["title"]
    if args.redo:
        for title in (letter, second):
            while job_id := find_job(store, title):
                store.delete_job(job_id)

    with server(work, data, APP_PORT, env) as app, server(work, blank, EMPTY_PORT, env) as empty:
        job_id = find_job(store, letter)
        if job_id is None:
            if not dotenv(key_variable(args.preset)):
                sys.exit(f"no drafts yet and no {key_variable(args.preset)} for {args.preset}")
            job_id = make_job(app, store, LETTER)
        summary = store.get_artifact(job_id, "summary", PipelineSummary)
        if summary is None:
            sys.exit(f"the job {job_id} has no summary")
        review = store.get_artifact(job_id, "review", ReviewState)
        if review is None or review.draft_version != summary.final_version:
            approve_first(app, store, job_id, APPROVED)
        if find_job(store, second) is None:
            make_job(app, store, SECOND)
        shots = pictures(app, empty, job_id)
        names = args.only or list(shots)
        with browser(args.browser) as b:
            for lang in args.langs:
                print(f"{lang}:")
                for base in (app, empty):  # the cookie is per host, but set it on both
                    b.go(f"{base}/ui/{lang}?next=/healthz", 0.2)
                for name in names:
                    if name == "03-progress":  # the running copy exists for this one alone
                        make_demo(db, job_id)
                    try:
                        shots[name](b)
                        picture = args.out / lang / f"{name}.webp"
                        b.shoot(picture)
                        if args.site:  # the same picture for the guide pages on the site
                            copy = args.site / "images" / "guide" / lang / picture.name
                            copy.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(picture, copy)
                    finally:
                        drop_demo(db)
    store.close()


if __name__ == "__main__":
    main()
