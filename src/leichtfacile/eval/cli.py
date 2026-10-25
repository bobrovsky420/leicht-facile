"""`python -m leichtfacile eval ...`: the evaluation commands.

fetch, calibrate and reference need no model; run needs a model endpoint
(`leichtfacile setup`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from leichtfacile.eval.dataset import MANIFEST
from leichtfacile.schemas import CONDITIONS


def add_eval_parser(sub: argparse._SubParsersAction) -> None:
    ev = sub.add_parser("eval", help="evaluation: fetch, calibrate, reference, run, report")
    evsub = ev.add_subparsers(dest="eval_command", required=True)

    def common(p: argparse.ArgumentParser, role: str = "eval") -> None:
        p.add_argument("--manifest", type=Path, default=MANIFEST)
        p.add_argument("--role", default=role, choices=["dev", "eval", "all"])
        p.add_argument("--lang", choices=["de", "fr", "it"])
        p.add_argument("--ids", nargs="*", help="only these pair ids")

    fetch = evsub.add_parser("fetch", help="download and cache the pairs (no model)")
    common(fetch, "all")
    fetch.add_argument("--refresh", action="store_true", help="fetch again even if cached")
    fetch.set_defaults(handler=_fetch)

    cal = evsub.add_parser("calibrate", help="rule checker on the official easy texts (no model)")
    common(cal, "all")
    cal.add_argument("--level", choices=["A2", "B1"], default="A2")
    cal.add_argument("--examples", action="store_true", help="print example findings (local only)")
    cal.set_defaults(handler=_calibrate)

    ref = evsub.add_parser("reference", help="score the originals and official versions (no model)")
    common(ref, "all")
    ref.add_argument("--results", type=Path, default=Path("eval/results"))
    ref.set_defaults(handler=_reference)

    run = evsub.add_parser("run", help="run a condition over the pairs (needs the endpoint)")
    common(run)
    run.add_argument("--condition", choices=list(CONDITIONS), required=True)
    run.add_argument("--writer", help="writer model (default: llm.models.writer)")
    run.add_argument(
        "--understand",
        help="model for the Understand stage (default: llm.models.understand, else the writer)",
    )
    run.add_argument("--judge", help="judge model (default: llm.models.judge)")
    run.add_argument("--judge-all", action="store_true", help="also judge P0 and P1 outputs")
    run.add_argument("--limit", type=int, help="at most this many pairs")
    run.add_argument(
        "--redo", action="store_true", help="run pairs again even when they have a result"
    )
    run.add_argument("--results", type=Path, default=Path("eval/results"))
    run.add_argument("--endpoint", help="a saved endpoint for this run (default: llm.endpoint)")
    run.add_argument(
        "--cache", action="store_true", help="reuse cached answers (llm.cache), cheap reruns"
    )
    run.set_defaults(handler=_run)

    smp = evsub.add_parser("sample", help="hand-labelling sheets for the judge (no model)")
    smp.add_argument("--results", type=Path, default=Path("eval/results"))
    smp.add_argument("--condition", default="P2", choices=["P0", "P1", "P2"])
    smp.add_argument("--role", default="eval", choices=["dev", "eval", "all"])
    smp.add_argument("--facts", type=int, default=30, help="(fact, draft) items")
    smp.add_argument("--blocks", type=int, default=30, help="blocks, half of them flagged")
    smp.add_argument("--seed", type=int, default=1)
    smp.add_argument("--out", type=Path, default=Path("eval/labels"))
    smp.set_defaults(handler=_sample)

    kap = evsub.add_parser("kappa", help="agreement between the judge and a filled sheet")
    kap.add_argument("sheet", type=Path, help="judge_facts.jsonl or judge_blocks.jsonl")
    kap.set_defaults(handler=_kappa)

    dia = evsub.add_parser(
        "diagnose", help="why must-keep facts are missing from the final drafts (no model)"
    )
    dia.add_argument("--results", type=Path, default=Path("eval/results"))
    dia.add_argument("--condition", default="P2", choices=["P1", "P2"])
    dia.add_argument("--role", default="dev", choices=["dev", "eval", "all"])
    dia.add_argument("--writer", help="only this writer model")
    dia.add_argument("--out", type=Path, help="write the full report (details) to this file")
    dia.add_argument("--json", type=Path, help="write the diagnosis as JSON to this file")
    dia.set_defaults(handler=_diagnose)

    res = evsub.add_parser(
        "rescore", help="score the stored jobs again from their artifacts (no model)"
    )
    res.add_argument("--manifest", type=Path, default=MANIFEST)
    res.add_argument("--results", type=Path, default=Path("eval/results"))
    res.add_argument("--condition", default="P2", choices=list(CONDITIONS))
    res.add_argument("--role", default="dev", choices=["dev", "eval", "all"])
    res.add_argument(
        "--in-place",
        action="store_true",
        help="replace the rows in the results folder (a baseline scored again, without "
        "sampling it again, against the newest P1 or P2 fact sheet of its pair)",
    )
    res.add_argument(
        "--select",
        default="facts",
        choices=["facts", "blocking"],
        help="the rule for the final version: facts (fewest missing must-keep values first, "
        "the pipeline's rule) or blocking (fewest blocking findings, the rule before 8 Oct)",
    )
    res.add_argument(
        "--out", type=Path, help="results folder to write (default: next to --results)"
    )
    res.set_defaults(handler=_rescore)

    rep = evsub.add_parser("report", help="Markdown tables from the results")
    rep.add_argument("--results", type=Path, default=Path("eval/results"))
    rep.add_argument("--role", default="eval", choices=["dev", "eval", "all"])
    rep.add_argument("--out", type=Path, help="write the tables to this file")
    rep.add_argument("--lang", choices=["de", "fr", "it"], help="only this language")
    rep.set_defaults(handler=_report)

    num = evsub.add_parser(
        "numbers", help="the headline numbers and their headline case (no model)"
    )
    num.add_argument("--results", type=Path, default=Path("eval/results"))
    num.add_argument("--role", default="eval", choices=["dev", "eval", "all"])
    num.add_argument("--lang", default="de", choices=["de", "fr", "it"])
    num.set_defaults(handler=_numbers)

    cmp = evsub.add_parser(
        "compare", help="fill docs/model-comparison.md from the runs it declares (no model)"
    )
    cmp.add_argument("--doc", type=Path, default=Path("docs/model-comparison.md"))
    cmp.add_argument("--role", default="eval", choices=["dev", "eval", "all"])
    cmp.set_defaults(handler=_compare)


def _pairs(args: argparse.Namespace):
    from leichtfacile.eval.dataset import load_manifest, select

    return select(load_manifest(args.manifest), role=args.role, lang=args.lang, ids=args.ids)


def _fetch(args: argparse.Namespace) -> int:
    from leichtfacile.eval.dataset import cache_dir, fetch_pairs

    pairs = _pairs(args)
    report = fetch_pairs(pairs, refresh=args.refresh)
    print(f"{len(pairs)} pairs: {len(report.fetched)} texts fetched, {len(report.cached)} cached, "
          f"{len(report.failed)} failed; cache: {cache_dir()}")  # fmt: skip
    for key, error in report.failed.items():
        print(f"  failed {key}: {error}", file=sys.stderr)
    return 1 if report.failed else 0


def _loaded(args: argparse.Namespace, side: str):
    from leichtfacile.eval.dataset import load_side

    docs, missing = [], []
    for pair in _pairs(args):
        try:
            docs.append((pair.id, load_side(pair, side)))
        except FileNotFoundError:
            missing.append(pair.id)
    if missing:
        print(f"not fetched yet: {', '.join(missing)}", file=sys.stderr)
    return docs


def _calibrate(args: argparse.Namespace) -> int:
    from leichtfacile.eval.calibrate import calibrate, render_calibration

    docs = _loaded(args, "easy")
    if not docs:
        print("no cached easy-language texts; run `eval fetch` first", file=sys.stderr)
        return 1
    print(render_calibration(calibrate(docs, args.level), show_examples=args.examples))
    return 0


def _reference(args: argparse.Namespace) -> int:
    from leichtfacile.eval.run import reference_rows

    pairs = [p for p in _pairs(args) if p.id in {pid for pid, _ in _loaded(args, "easy")}]
    path = reference_rows(pairs, args.results)
    print(f"reference rows for {len(pairs)} pairs: {path}")
    return 0


def _run(args: argparse.Namespace) -> int:
    from leichtfacile.cli import settings_or_exit
    from leichtfacile.eval.run import run_condition
    from leichtfacile.llm.client import LLMClient

    settings = settings_or_exit()
    pairs = _pairs(args)[: args.limit] if args.limit else _pairs(args)
    llm = LLMClient.from_settings(settings)
    path = run_condition(
        pairs, args.condition, settings=settings, llm=llm, results_dir=args.results,
        writer=args.writer, understand=args.understand, judge=args.judge,
        judge_all=args.judge_all, redo=args.redo,
    )  # fmt: skip
    print(f"results: {path}")
    return 0


def _sample(args: argparse.Namespace) -> int:
    from leichtfacile.eval.labels import sample_items, write_sheets

    fact_items, block_items = sample_items(
        args.results, condition=args.condition, role=args.role, facts=args.facts,
        blocks=args.blocks, seed=args.seed,
    )  # fmt: skip
    paths = write_sheets(args.out, fact_items, block_items)
    print(
        f"{len(fact_items)} fact items and {len(block_items)} block items: {paths[0]}, {paths[2]}"
    )
    print(
        "Fill the label field (facts: present, missing, distorted; blocks: supported, "
        "unsupported), then run `eval kappa <sheet>`."
    )
    return 0


def _kappa(args: argparse.Namespace) -> int:
    from leichtfacile.eval.labels import kappa_report, render_kappa

    print(render_kappa(kappa_report(args.sheet)))
    return 0


def _diagnose(args: argparse.Namespace) -> int:
    from leichtfacile.eval.diagnose import diagnose, render_diagnosis, to_json

    jobs = diagnose(args.results, condition=args.condition, role=args.role, writer=args.writer)
    if not jobs:
        print(f"no completed {args.condition} jobs for the {args.role} split in {args.results}")
        return 1
    title = f"Fact-retention diagnosis: {args.condition}, {args.role} split, {args.results}"
    # The counts can be published; the details quote the pages and stay local.
    print(render_diagnosis(jobs, title=title, details=False))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_diagnosis(jobs, title=title), encoding="utf-8")
        print(f"written: {args.out}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(to_json(jobs) + "\n", encoding="utf-8")
        print(f"written: {args.json}")
    return 0


def _rescore(args: argparse.Namespace) -> int:
    from leichtfacile.eval.dataset import load_manifest
    from leichtfacile.eval.run import rescore

    out = rescore(
        args.results,
        pairs=load_manifest(args.manifest),
        condition=args.condition,
        role=args.role,
        select=args.select,
        out_dir=args.out,
        in_place=args.in_place,
    )
    print(
        f"rescored rows: {out} (render them with: eval report --results {out} --role {args.role})"
    )
    return 0


def _numbers(args: argparse.Namespace) -> int:
    from leichtfacile.eval.numbers import render_numbers

    print(render_numbers(args.results, role=args.role, lang=args.lang))
    return 0


def _compare(args: argparse.Namespace) -> int:
    from leichtfacile.eval.compare import update

    runs = update(args.doc, role=args.role)
    print(f"{args.doc}: the tables of {runs} runs written")
    return 0


def _report(args: argparse.Namespace) -> int:
    from leichtfacile.eval.report import render_report

    text = render_report(args.results, role=args.role, lang=args.lang)
    if args.out:
        # The file is a page of the documentation (docs/evaluation.md): a title, and
        # where the tables come from, so that nobody edits it by hand.
        source = args.results.as_posix()
        head = (
            "# Evaluation tables\n\n"
            f"Written by `python -m leichtfacile eval report` from `{source}`; do not edit\n"
            "by hand.\n\n"
        )
        args.out.write_text(head + text + "\n", encoding="utf-8")
        print(f"written: {args.out}")
    else:
        print(text)
    return 0
