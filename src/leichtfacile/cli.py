"""Command line: `python -m leichtfacile <command>`.

- `serve`      run the web application
- `check-llm`  list the endpoint's models and make one short call
- `ingest`     print the segments of a file or URL
- `check`      run the rule checker on an existing easy-language text
- `simplify`   run the pipeline on a file or URL and write all artifacts to a folder
- `eval`       evaluation: fetch pairs, calibrate the checker, run conditions, report
- `examples`   build the example jobs shown on first start
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from leichtfacile import __version__
from leichtfacile.schemas import CONDITIONS, canonical_condition


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leichtfacile", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    check_llm = sub.add_parser("check-llm", help="list models and make one short call")
    check_llm.add_argument("--model", help="model name (default: LLM_NAME)")
    check_llm.add_argument("--thinking", action="store_true", help="use thinking mode")

    ingest = sub.add_parser("ingest", help="print the segments of a file or URL")
    ingest.add_argument("input", help="file path or http(s) URL")
    ingest.add_argument("--lang", choices=["de", "fr", "it"])
    ingest.add_argument("--section", help="keep only the section under this heading")
    ingest.add_argument("--json", action="store_true", help="print the SourceDocument as JSON")

    check = sub.add_parser("check", help="run the rule checker on an easy-language text")
    check.add_argument("input", help="file path or http(s) URL")
    check.add_argument("--lang", choices=["de", "fr", "it"])
    check.add_argument("--level", choices=["A2", "B1"], default="A2")
    check.add_argument("--section", help="keep only the section under this heading")
    check.add_argument("--json", action="store_true", help="print the findings as JSON")

    simplify = sub.add_parser("simplify", help="run the pipeline on a file or URL")
    simplify.add_argument("input", help="file path or http(s) URL")
    simplify.add_argument("--lang", choices=["de", "fr", "it"])
    simplify.add_argument("--level", choices=["A2", "B1"], default="A2")
    simplify.add_argument(
        "--condition", type=canonical_condition, choices=list(CONDITIONS), default="P2"
    )
    simplify.add_argument("--out", type=Path, default=Path("out"), help="output folder")
    simplify.add_argument("--writer", help="writer model (default: LLM_NAME)")
    simplify.add_argument(
        "--understand",
        help="model for the Understand stage (default: LLM_UNDERSTAND_NAME, else the writer)",
    )
    simplify.add_argument("--judge", help="judge model (default: LLM_JUDGE_NAME)")
    simplify.add_argument("--no-judge", action="store_true", help="P2 without the judge")
    simplify.add_argument("--no-repair", action="store_true", help="P2 without repair rounds")
    simplify.add_argument(
        "--mode",
        choices=["standard", "decision"],
        default="standard",
        help="decision: the letter that goes out with a decision (docs/use-case-decisions.md)",
    )
    simplify.add_argument("--addressee", help="decision mode: the person the letter speaks to")
    simplify.add_argument("--notice", help="decision mode: the authority's fixed notice")
    simplify.add_argument(
        "--stop-after", choices=["understand", "write", "check", "judge"], help="stop early"
    )

    examples = sub.add_parser("examples", help="build the example jobs (needs the endpoint)")
    examples.add_argument("action", choices=["build"])
    examples.add_argument("--level", choices=["A2", "B1"], default="A2")
    examples.add_argument(
        "--only", nargs="+", metavar="NAME", help="build these sources only (file name, no suffix)"
    )

    from leichtfacile.eval.cli import add_eval_parser

    add_eval_parser(sub)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "check-llm":
        return _check_llm(args.model, args.thinking)
    if args.command == "ingest":
        return _ingest(args)
    if args.command == "check":
        return _check(args)
    if args.command == "simplify":
        return _simplify(args)
    if args.command == "eval":
        return args.handler(args)
    if args.command == "examples":
        from leichtfacile.examples import build_examples

        written = build_examples(level=args.level, only=args.only)
        for path in written:
            print(f"written: {path}")
        return 0 if written else 1
    parser.error(f"unknown command {args.command}")
    return 2


def _serve(host: str, port: int) -> int:
    import uvicorn

    uvicorn.run("leichtfacile.web.app:create_app", factory=True, host=host, port=port)
    return 0


def _check_llm(model: str | None, thinking: bool) -> int:
    from leichtfacile.config import get_settings
    from leichtfacile.llm.client import LLMClient, LLMError

    settings = get_settings()
    client = LLMClient(settings)
    name, extra = client.resolve_model(model, thinking)
    print(f"endpoint:  {settings.llm_base_url}")
    print(f"model:     {name} {extra or ''}".rstrip())

    try:
        models = client.list_models()
        print(f"listed:    {len(models)} models; requested model listed: {name in models}")
        for m in models:
            print(f"           - {m}")
    except Exception as exc:
        print(f"listing models failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    try:
        result = client.complete(
            [{"role": "user", "content": "Wie viel ist 17 + 25? Antworte nur mit der Zahl."}],
            model=model,
            thinking=thinking,
            max_tokens=2048,
            stage="check",
        )
    except LLMError as exc:
        print(f"call failed: {exc}", file=sys.stderr)
        return 1
    u = result.usage
    print(f"answer:    {result.text!r}")
    print(
        f"reasoning: {'yes' if result.reasoning else 'no'}"
        f"{f' ({len(result.reasoning)} chars)' if result.reasoning else ''}"
    )
    print(f"finish:    {result.finish_reason}")
    print(f"tokens:    {u.tokens_in} in, {u.tokens_out} out, {u.latency_ms} ms")
    return 0 if result.text.strip() else 1


def load_source(path_or_url: str, lang: str | None, section: str | None = None):
    from leichtfacile import ingest

    if path_or_url.lower().startswith(("http://", "https://")):
        doc = ingest.ingest_url(path_or_url, lang=lang)
    else:
        doc = ingest.ingest_file(Path(path_or_url), lang=lang)
    if section:
        doc = ingest.select_section(doc, section)
    return doc


def _ingest(args: argparse.Namespace) -> int:
    from leichtfacile.ingest.errors import IngestError

    try:
        doc = load_source(args.input, args.lang, args.section)
    except (IngestError, OSError) as exc:
        print(f"cannot read {args.input}: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(doc.model_dump_json(indent=2))
        return 0
    print(f"{doc.id}  lang={doc.lang}  title={doc.title!r}  segments={len(doc.segments)}  "
          f"words={doc.word_count()}")  # fmt: skip
    for seg in doc.segments:
        marker = {"heading": "#" * (seg.heading_level or 1) + " ", "list_item": "- "}.get(
            seg.kind, ""
        )
        page = f" p{seg.page}" if seg.page else ""
        print(f"{seg.id}{page}  {marker}{seg.text}")
    return 0


def _check(args: argparse.Namespace) -> int:
    from leichtfacile.eval.calibrate import source_as_draft
    from leichtfacile.ingest.errors import IngestError
    from leichtfacile.rules import check_draft

    try:
        doc = load_source(args.input, args.lang, args.section)
    except (IngestError, OSError) as exc:
        print(f"cannot read {args.input}: {exc}", file=sys.stderr)
        return 1
    draft = source_as_draft(doc, args.level)
    result = check_draft(draft)
    if args.json:
        print(result.model_dump_json(indent=2))
        return 0
    blocks = {b.id: b for b in draft.blocks}
    for f in result.findings:
        where = f"{f.block_id} " if f.block_id else ""
        print(f"{f.severity:5} {f.rule_id:8} {where}{f.message}")
        if f.block_id:
            print(f"      | {blocks[f.block_id].text[:110]}")
        if f.suggestion:
            print(f"      > {f.suggestion}")
    per_100 = 100 / max(1, len(draft.blocks))
    counts = Counter(f.severity for f in result.findings)
    m = result.metrics
    print(
        f"\n{len(draft.blocks)} blocks, {m.sentences} sentences, {m.avg_words} words per sentence, "
        f"readability {m.readability} ({m.readability_formula})"
    )
    print(
        "per 100 blocks: "
        + ", ".join(f"{counts[s] * per_100:.1f} {s}" for s in ("error", "warn", "info"))
    )
    return 0


def _simplify(args: argparse.Namespace) -> int:
    from leichtfacile.config import get_settings
    from leichtfacile.export.bundle import build_bundle
    from leichtfacile.export.html import to_html
    from leichtfacile.export.markdown import to_markdown
    from leichtfacile.ingest.errors import IngestError
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.orchestrator import Orchestrator
    from leichtfacile.schemas import Draft, JobConfig, PipelineSummary
    from leichtfacile.store import Store

    settings = get_settings()
    try:
        source = load_source(args.input, args.lang)
    except (IngestError, OSError) as exc:
        print(f"cannot read {args.input}: {exc}", file=sys.stderr)
        return 1
    store = Store(settings.data_dir / "leichtfacile.sqlite")
    config = JobConfig(
        lang=source.lang,
        level=args.level,
        condition=args.condition,
        writer_model=args.writer,
        understand_model=args.understand,
        judge_model=args.judge,
        use_judge=not args.no_judge,
        max_repair_rounds=0 if args.no_repair else settings.max_repair_rounds,
        max_facts_rounds=0 if args.no_repair else settings.max_facts_rounds,
        mode=args.mode,
        addressee=args.addressee,
        notice=args.notice,
    )
    job = store.create_job(config, title=source.title or args.input)
    store.put_artifact(job.id, "source", source)
    llm = LLMClient.from_settings(settings)
    Orchestrator(store, llm, settings).run(job.id, stop_after=args.stop_after)
    job = store.get_job(job.id)

    out = args.out / job.id
    out.mkdir(parents=True, exist_ok=True)
    bundle = build_bundle(store, job)
    (out / "bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = store.get_artifact(job.id, "summary", PipelineSummary)
    version = summary.final_version if summary else None
    draft = store.get_artifact(job.id, "draft", Draft, version=version)
    if draft is not None:
        notice = job.config.notice
        markdown = to_markdown(draft, title=job.title, notice=notice)
        (out / "draft.md").write_text(markdown, encoding="utf-8")
        html = to_html(draft, title=job.title, notice=notice)
        (out / "draft.html").write_text(html, encoding="utf-8")
    tokens = sum(u.tokens_in + u.tokens_out for u in job.usage)
    print(
        f"job {job.id}: {job.status} ({job.stage}); {len(job.usage)} model calls, {tokens} tokens"
    )
    if job.error:
        print(f"error: {job.error}", file=sys.stderr)
    print(f"artifacts: {out}")
    return 0 if job.status in ("needs_review", "done") else 1


if __name__ == "__main__":
    raise SystemExit(main())
