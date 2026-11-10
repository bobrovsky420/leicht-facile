"""Export replay cases of the repair rounds from a job store into tests/fixtures/repairs/.

A case is one recorded round (`RepairRecord`) of a job on a shipped example letter
(src/leichtfacile/letters/): the draft version the round started from, the job's fact
sheet, what the round asked for, the model's answer as code applied it, and what
`versions.apply_repairs` makes of it with the code of today, the new version and the
sentences left out. tests/pipeline/test_repair_replay.py replays every case and
compares, so a change of the function that alters an output fails there; a deliberate
change exports the cases again in the same commit, and the diff of the fixtures shows
the reviewer what changed.

    uv run python scripts/repair_fixtures.py [--data data] [--out tests/fixtures/repairs] [--all]

The answer comes from the response cache (`llm.cache = true` while the jobs ran): a
record from before 4 November 2026 keeps the answer's texts but not the block kind and
the cited sentences of an addition, which the function reads too, and the cached answer
has every field. The cached repair answers of a job are parsed and given to its records
in call order, each record the first unused answer with its texts. The calls right after
that answer with the same texts are retries of the same round (an answer the checks sent
back); when one of them differs in a field the function reads, only the checks could
tell which was applied, and the round is left out as ambiguous. Of the replayable rounds
the script keeps a small set, chosen greedily, that runs every branch of versions.py
coverage.py measures (an alternative on one line is no branch to it, so a few shapes of
answer are picked by name as well), plus one round per variety and round kind and one
per letter; --all keeps every one. The letters are invented, so the fixtures carry no
personal data. The store and the cache are opened read-only: a store older than schema
1 has no cache keys (open it with the app once, which migrates it with a backup), one
newer than the app's is refused.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import coverage
from pydantic import ValidationError

from leichtfacile import __version__
from leichtfacile.config import LETTERS_DIR
from leichtfacile.llm.json_out import JSONExtractionError, extract_json
from leichtfacile.pipeline import versions
from leichtfacile.pipeline.models import RepairOut
from leichtfacile.pipeline.versions import (
    RepairRequest,
    apply_repairs,
    sentences_of,
    without_texts,
)
from leichtfacile.schemas import Draft, DroppedText, FactSheet, RepairRecord, SourceDocument
from leichtfacile.store import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "repairs"
FORMAT = "repair-replay@1"
VERSIONS_FILE = str(Path(versions.__file__).resolve())
CACHE_KEYS_SINCE = 1  # the schema version from which every model call keeps its cache key


@dataclass
class Answer:
    position: int  # among the job's model calls, in order: a retry follows its call
    model: str
    out: RepairOut


@dataclass
class Case:
    name: str
    job: str
    letter: str
    model: str
    recorded: str  # the day the job ran
    kind: str
    version: int
    draft: Draft
    factsheet: FactSheet
    blocks: list[str]
    facts: list[str]
    answer: dict  # the RepairOut as code applied it, before the replay touches it
    recorded_dropped: list[dict]  # what the record says was left out, examples apart
    expected: dict = field(default_factory=dict)
    arcs: set[tuple[int, int]] = field(default_factory=set)
    differs: bool = False  # today's dropped list is not the recorded one

    @property
    def size(self) -> int:
        return len(self.draft.blocks)

    @property
    def variety(self) -> str:
        return self.draft.variety

    def shapes(self) -> set[str]:
        """What the answer and the output show of the function's rules: the picks
        `choose` makes by name, for the alternatives line coverage does not see."""
        lang = self.draft.lang
        by_id = self.draft.by_id()
        repairs, additions = self.answer["repairs"], self.answer["additions"]
        dropped = self.expected["dropped"]
        found = {f"a sentence dropped as {d['reason']}" for d in dropped}
        repaired = {t for r in repairs for t in sentences_of(list(r["texts"]), lang)}
        if any(d["reason"] == "repeat" and d["text"] in repaired for d in dropped):
            found.add("a repair text dropped as a repeat")
        if any(len(r["texts"]) > 1 for r in repairs):
            found.add("a block repaired with several texts")
        anchors = [by_id.get(a["after"]) if a["after"] else None for a in additions]
        if None in anchors:
            found.add("an addition without a block to follow")
        if any(b is not None and b.kind == "list_item" for b in anchors):
            found.add("an addition after a list item")
        if any(a["kind"] != "sentence" for a in additions):
            found.add("an addition that is no sentence")
        return found


def _collapse(text: str) -> str:
    return " ".join(text.split())


def letters() -> dict[str, str]:
    paths = sorted(LETTERS_DIR.glob("*.txt"))
    return {p.name: _collapse(p.read_text(encoding="utf-8")) for p in paths}


def letter_of(source: SourceDocument, shipped: dict[str, str]) -> str | None:
    """The shipped letter the job ran on: the one whose text holds the source's
    longest paragraph (ingest keeps the words of a text file)."""
    longest = max((s.text for s in source.segments), key=len, default="")
    probe = _collapse(longest)
    if not probe:
        return None
    return next((name for name, text in shipped.items() if probe in text), None)


def _read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"{path}: no such file")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_schema(store: sqlite3.Connection, path: Path) -> None:
    version = int(store.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise SystemExit(
            f"{path}: schema {version}, this version reads up to {SCHEMA_VERSION}: update the app"
        )
    if version < CACHE_KEYS_SINCE:
        raise SystemExit(
            f"{path}: schema {version} keeps no cache keys: open the store with the app once "
            "(it migrates the store and keeps a backup), then export"
        )
    print(f"{path}: schema {version} (the app's is {SCHEMA_VERSION})")


def answers(store: sqlite3.Connection, cache: sqlite3.Connection, job_id: str) -> list[Answer]:
    """The job's cached repair-stage answers that parse, in call order, each with its
    position among all the job's calls."""
    rows = store.execute(
        "SELECT stage, model, cache_key FROM llm_calls WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    found: list[Answer] = []
    for position, row in enumerate(rows):
        if row["stage"].split()[0] != "repair" or not row["cache_key"]:
            continue
        hit = cache.execute(
            "SELECT response FROM llm_cache WHERE key = ?", (row["cache_key"],)
        ).fetchone()
        if hit is None:
            continue
        response = json.loads(hit["response"])
        if response.get("finish_reason") == "length":
            continue  # cut off: never applied
        try:
            out = RepairOut.model_validate(extract_json(response["text"], RepairOut.model_fields))
        except (JSONExtractionError, ValidationError):
            continue  # an answer the model was asked to correct
        found.append(Answer(position, row["model"], out))
    return found


def same_answer(record: RepairRecord, out: RepairOut) -> bool:
    """Whether the cached answer is the record's: the same blocks and texts and, where
    the record names them (records since 4 November 2026), the kind and the cited
    sentences of every addition."""
    if [(r.block_id, r.texts) for r in record.repairs] != [(r.id, r.texts) for r in out.repairs]:
        return False
    if len(record.additions) != len(out.additions):
        return False
    return all(
        (a.after, a.texts, a.fact_ids) == (b.after, b.texts, b.fact_ids)
        and a.kind in ("sentence", b.kind)
        and (not a.segment_ids or a.segment_ids == b.segment_ids)
        for a, b in zip(record.additions, out.additions, strict=True)
    )


def answer_of(record: RepairRecord, candidates: list[Answer], used: set[int]) -> Answer | str:
    """The cached answer the round applied, or why there is none: the first unused
    answer with the record's texts. The calls right after it with the same texts are
    retries of the same round; when one differs in a field the function reads, the
    round is ambiguous (only the checks could tell which answer was applied)."""
    matches = [a for a in candidates if a.position not in used and same_answer(record, a.out)]
    if not matches:
        return "round whose answer is not in the cache"
    run = [matches[0]]
    for a in matches[1:]:
        if a.position != run[-1].position + 1:
            break
        run.append(a)
    used.update(a.position for a in run)
    if any(a.out.model_dump() != run[0].out.model_dump() for a in run[1:]):
        return "round whose answer is ambiguous in the cache"
    return run[0]


def without_examples(out: RepairOut, record: RepairRecord) -> RepairOut:
    """The answer as `apply_repairs` saw it: the example sentences `stages.repair`
    drops before it (`DroppedText.reason == "example"`) taken out, on a copy."""
    return without_texts(out, {d.text for d in record.dropped if d.reason == "example"})


def artifact(
    store: sqlite3.Connection, job_id: str, name: str, version: int | None = None
) -> dict | None:
    sql = "SELECT data FROM artifacts WHERE job_id = ? AND name = ?"
    params: tuple = (job_id, name)
    if version is not None:
        sql += " AND version = ?"
        params = (*params, version)
    row = store.execute(sql + " ORDER BY version DESC LIMIT 1", params).fetchone()
    return json.loads(row["data"]) if row else None


def collect(
    store: sqlite3.Connection, cache: sqlite3.Connection, shipped: dict[str, str]
) -> list[Case]:
    """Every replayable round of every job on a shipped letter, without the expected
    output; what was skipped is printed."""
    cases: list[Case] = []
    skipped: dict[str, int] = {}
    jobs = store.execute(
        "SELECT id, created_at FROM jobs WHERE id IN (SELECT DISTINCT job_id FROM artifacts "
        "WHERE name = 'repair') ORDER BY created_at, id"
    ).fetchall()
    for job in jobs:
        source_json = artifact(store, job["id"], "source")
        factsheet_json = artifact(store, job["id"], "factsheet")
        if source_json is None or factsheet_json is None:
            why = "job without source or fact sheet"
            skipped[why] = skipped.get(why, 0) + 1
            continue
        letter = letter_of(SourceDocument.model_validate(source_json), shipped)
        if letter is None:
            skipped["job on another document"] = skipped.get("job on another document", 0) + 1
            continue
        factsheet = FactSheet.model_validate(factsheet_json)
        cases += rounds(store, cache, job, letter, factsheet, skipped)
    for why, n in sorted(skipped.items()):
        print(f"skipped: {n} {why}")
    return cases


def rounds(
    store: sqlite3.Connection,
    cache: sqlite3.Connection,
    job: sqlite3.Row,
    letter: str,
    factsheet: FactSheet,
    skipped: dict[str, int],
) -> list[Case]:
    """The replayable rounds of one job, in order."""
    cases: list[Case] = []
    facts = factsheet.fact_ids()
    candidates = answers(store, cache, job["id"])
    used: set[int] = set()
    versions = store.execute(
        "SELECT version FROM artifacts WHERE job_id = ? AND name = 'repair' ORDER BY version",
        (job["id"],),
    ).fetchall()
    for row in versions:
        record = RepairRecord.model_validate(artifact(store, job["id"], "repair", row["version"]))
        if record.kind == "recover":
            continue  # the recover round places its sentences with add_sentences
        parent = artifact(store, job["id"], "draft", record.parent_version)
        found = answer_of(record, candidates, used)
        lacking = any(f not in facts for f in record.requested_facts)
        if lacking or parent is None or isinstance(found, str):
            why = (
                "round asking for a fact the sheet lacks"
                if lacking
                else "round without its parent version"
                if parent is None
                else str(found)
            )
            skipped[why] = skipped.get(why, 0) + 1
            continue
        cases.append(
            Case(
                name=f"{Path(letter).stem}-{job['id'][:8]}-v{record.draft_version:02d}-{record.kind}",
                job=job["id"],
                letter=letter,
                model=found.model,
                recorded=str(job["created_at"])[:10],
                kind=record.kind,
                version=record.draft_version,
                draft=Draft.model_validate(parent),
                factsheet=factsheet,
                blocks=list(record.requested_blocks),
                facts=list(record.requested_facts),
                answer=without_examples(found.out, record).model_dump(mode="json"),
                recorded_dropped=[
                    d.model_dump(mode="json") for d in record.dropped if d.reason != "example"
                ],
            )
        )
    return cases


def replay_one(case: Case) -> tuple[Draft, list[DroppedText]]:
    """The round as the test replays it (tests/pipeline/test_repair_replay.py)."""
    facts = {f.id: f for f in case.factsheet.facts}
    request = RepairRequest({b: ["replay"] for b in case.blocks}, [facts[i] for i in case.facts])
    out = RepairOut.model_validate(case.answer)
    dropped: list[DroppedText] = []
    draft = apply_repairs(
        case.draft, out, request, case.factsheet, dropped=dropped, version=case.version
    )
    return draft, dropped


def replay(cases: list[Case]) -> None:
    """Fill in the expected output of every case, measuring which branches of versions.py
    each one runs."""
    # The checkout's coverage settings (pyproject.toml) are for the test suite; the
    # C tracer, since the sys.monitoring one keeps no contexts.
    cov = coverage.Coverage(branch=True, data_file=None, include=[VERSIONS_FILE], config_file=False)
    cov.set_option("run:core", "ctrace")
    cov.start()
    try:
        for case in cases:
            cov.switch_context(case.name)
            draft, dropped = replay_one(case)
            case.expected = {
                "draft": draft.model_dump(mode="json"),
                "dropped": [d.model_dump(mode="json") for d in dropped],
            }
            case.differs = case.expected["dropped"] != case.recorded_dropped
    finally:
        cov.stop()
    data = cov.get_data()
    for case in cases:
        data.set_query_context(case.name)
        case.arcs = set(data.arcs(VERSIONS_FILE) or [])
    universe = set().union(*(c.arcs for c in cases)) if cases else set()
    print(f"{len(universe)} branches of versions.py run by the rounds")


def choose(cases: list[Case]) -> list[Case]:
    """A small set of cases, chosen greedily, that runs every branch any case runs,
    plus one case per shape of answer (`Case.shapes`), per variety and round kind,
    and per letter."""
    universe: set[tuple[int, int]] = set().union(*(c.arcs for c in cases))
    chosen: list[Case] = []
    covered: set[tuple[int, int]] = set()
    left = list(cases)
    while covered != universe and left:
        best = max(left, key=lambda c: (len(c.arcs - covered), -c.size, c.name))
        if not best.arcs - covered:
            break
        chosen.append(best)
        covered |= best.arcs
        left.remove(best)
    traits = {c.name: c.shapes() | {(c.variety, c.kind), (c.letter, "")} for c in cases}
    for trait in sorted(set().union(*traits.values()), key=str):
        if any(trait in traits[c.name] for c in chosen):
            continue
        more = [c for c in left if trait in traits[c.name]]
        chosen.append(min(more, key=lambda c: c.size))
        left.remove(chosen[-1])
    return sorted(chosen, key=lambda c: c.name)


def write(cases: list[Case], out_dir: Path, *, everything: bool, total: int) -> None:
    """The cases as JSON files, one each, and the README; only files of this format
    are replaced, any other JSON file in the folder stops the export."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        if json.loads(old.read_text(encoding="utf-8")).get("format") != FORMAT:
            raise SystemExit(f"{old}: not a replay case, refusing to write into {out_dir}")
        old.unlink()
    for case in cases:
        payload = {
            "format": FORMAT,
            "exported_with": __version__,
            "job": case.job,
            "letter": case.letter,
            "model": case.model,
            "recorded": case.recorded,
            "kind": case.kind,
            "version": case.version,
            "requested_blocks": case.blocks,
            "requested_facts": case.facts,
            "draft": case.draft.model_dump(mode="json"),
            "factsheet": case.factsheet.model_dump(mode="json"),
            "answer": case.answer,
            "expected": case.expected,
            "recorded_dropped": case.recorded_dropped,
        }
        text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
        (out_dir / f"{case.name}.json").write_text(text, encoding="utf-8", newline="\n")
    text = readme(cases, everything=everything, total=total)
    (out_dir / "README.md").write_text(text, encoding="utf-8", newline="\n")


def readme(cases: list[Case], *, everything: bool, total: int) -> str:
    rows = "\n".join(
        f"| `{c.name}` | {c.letter} | {c.kind} | {c.model} | {c.recorded} | {c.size} | "
        f"{len(c.expected['draft']['blocks'])} | {len(c.expected['dropped'])} | "
        f"{'yes' if c.differs else ''} |"
        for c in cases
    )
    kept = (
        f"all {total} replayable rounds of the store"
        if everything
        else f"{len(cases)} of the {total} replayable rounds of the store: a small set, chosen "
        "greedily, that runs every branch of `versions.py` any of them runs, plus one round "
        "per shape of answer, per variety and round kind, and per letter"
    )
    return f"""# Recorded repair rounds

Replay cases of `versions.apply_repairs`, the function that makes the new draft version
out of a repair round's answer: for each, the version the round started from, the
job's fact sheet, the blocks and facts the round asked for, the model's answer as code
applied it (the example sentences `stages.repair` drops already taken out), and what
the function made of it with the code of the day of the export, the new version and
the sentences left out with their reasons. `tests/pipeline/test_repair_replay.py`
replays every case and compares both outputs, so a change of the function that alters
an output fails there. A deliberate change exports the cases again in the same commit
(`uv run python scripts/repair_fixtures.py`, from the job store of a checkout with
`llm.cache = true`), and the diff of the fixtures shows the reviewer what changed.

The rounds are real answers of the models named below on the shipped example letters
(`src/leichtfacile/letters/`, invented senders and people); the jobs ran on the days
named. The expected outputs are not what the pipeline stored then: the function is
replayed with the current code at the export, and a case marked in the last column
has a list of dropped sentences unlike the one its record holds (`recorded_dropped` in
the file), the rules that changed since the job ran. The sentence splitting the
function uses comes from the spaCy models the package depends on, so a model bump that
moves a sentence boundary shows up here first; the stems it compares are the first
letters of the words, no model.

Kept: {kept}. Exported with {__version__}.

| Case | Letter | Kind | Model | Day | Blocks in | Blocks out | Dropped | Differs |
|------|--------|------|-------|-----|-----------|------------|---------|---------|
{rows}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="the data folder")
    parser.add_argument("--out", type=Path, default=OUT, help="the fixtures folder")
    parser.add_argument("--all", action="store_true", help="keep every replayable round")
    args = parser.parse_args()
    store_path = args.data / "leichtfacile.sqlite"
    store = _read_only(store_path)
    check_schema(store, store_path)
    cache = _read_only(args.data / "llm_cache.sqlite")
    cases = collect(store, cache, letters())
    if not cases:
        raise SystemExit(f"{store_path}: no replayable round")
    replay(cases)
    differing = sum(c.differs for c in cases)
    print(
        f"{len(cases)} replayable rounds, {differing} with a dropped list unlike the recorded one"
    )
    chosen = cases if args.all else choose(cases)
    write(chosen, args.out, everything=args.all, total=len(cases))
    size = sum(p.stat().st_size for p in args.out.glob("*.json"))
    print(f"{args.out}: {len(chosen)} cases written, {size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
