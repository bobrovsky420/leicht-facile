"""`python -m leichtfacile eval ...`: the evaluation commands.

fetch, calibrate and reference need no model; run needs the endpoint in .env.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from leichtfacile.eval.dataset import MANIFEST
from leichtfacile.schemas import CONDITIONS, canonical_condition


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
    run.add_argument(
        "--condition", type=canonical_condition, choices=list(CONDITIONS), required=True
    )
    run.add_argument("--writer", help="writer model (default: LLM_NAME)")
    run.add_argument(
        "--understand",
        help="model for the Understand stage (default: LLM_UNDERSTAND_NAME, else the writer)",
    )
    run.add_argument("--judge", help="judge model (default: LLM_JUDGE_NAME)")
    run.add_argument("--judge-all", action="store_true", help="also judge P0 and P1 outputs")
    run.add_argument("--limit", type=int, help="at most this many pairs")
    run.add_argument(
        "--redo", action="store_true", help="run pairs again even when they have a result"
    )
    run.add_argument("--results", type=Path, default=Path("eval/results"))
    run.set_defaults(handler=_run)

    smp = evsub.add_parser("sample", help="hand-labelling sheets for the judge (no model)")
    smp.add_argument("--results", type=Path, default=Path("eval/results"))
    smp.add_argument(
        "--condition", type=canonical_condition, default="P2", choices=["P0", "P1", "P2"]
    )
    smp.add_argument("--role", default="eval", choices=["dev", "eval", "all"])
    smp.add_argument("--facts", type=int, default=30, help="(fact, draft) items")
    smp.add_argument("--blocks", type=int, default=30, help="blocks, half of them flagged")
    smp.add_argument("--seed", type=int, default=1)
    smp.add_argument("--out", type=Path, default=Path("eval/labels"))
    smp.set_defaults(handler=_sample)

    kap = evsub.add_parser("kappa", help="agreement between the judge and a filled sheet")
    kap.add_argument("sheet", type=Path, help="judge_facts.jsonl or judge_blocks.jsonl")
    kap.set_defaults(handler=_kappa)

    rep = evsub.add_parser("report", help="Markdown tables from the results")
    rep.add_argument("--results", type=Path, default=Path("eval/results"))
    rep.add_argument("--role", default="eval", choices=["dev", "eval", "all"])
    rep.add_argument("--out", type=Path, help="write the tables to this file")
    rep.add_argument("--lang", choices=["de", "fr", "it"], help="only this language")
    rep.set_defaults(handler=_report)


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
    from leichtfacile.config import get_settings
    from leichtfacile.eval.run import run_condition
    from leichtfacile.llm.client import LLMClient

    settings = get_settings()
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


def _report(args: argparse.Namespace) -> int:
    from leichtfacile.eval.report import render_report

    text = render_report(args.results, role=args.role, lang=args.lang)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"written: {args.out}")
    else:
        print(text)
    return 0
