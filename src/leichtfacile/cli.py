"""Command line: `leichtfacile <command>` (or `python -m leichtfacile <command>`).

- `setup`      ask for a model endpoint, save it in the config file, get the models
- `endpoint`   list the saved endpoints, pick the one in use, remove one
- `config`     show the settings and their sources, set, unset or edit them
- `models`     download (or unpack) the spaCy models for German and French
- `serve`      run the web application and open it in the browser
- `check-llm`  list the endpoint's models and make one short call
- `ingest`     print the segments of a file or URL
- `check`      run the rule checker on an existing easy-language text
- `simplify`   run the pipeline on a file or URL and write all artifacts to a folder
- `eval`       evaluation: fetch pairs, calibrate the checker, run conditions, report
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from leichtfacile import __version__, configure
from leichtfacile.config import PRESETS, ConfigError, use_overrides
from leichtfacile.schemas import CONDITIONS

if TYPE_CHECKING:
    from leichtfacile.config import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leichtfacile", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--config",
        type=Path,
        help="the settings file (default: LEICHTFACILE_CONFIG, else the user's config.toml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="set up a model endpoint and use it")
    setup.add_argument(
        "endpoint",
        nargs="?",
        help=f"a preset ({', '.join(PRESETS)}) or a name for another endpoint",
    )
    setup.add_argument(
        "--preset", choices=list(PRESETS), help="the preset the endpoint starts from"
    )
    setup.add_argument("--name", help="the endpoint's name in the file (default: the preset's)")
    setup.add_argument("--base-url", help="the endpoint's address (OpenAI-compatible)")
    setup.add_argument(
        "--api-key",
        help="the key, saved in the .env next to the config file; it ends up in the shell "
        "history, so leave it out to be asked",
    )
    setup.add_argument("--api-key-env", help="the variable that holds the key (nothing saved)")
    setup.add_argument("--model", help="the model that reads, writes and repairs")
    setup.add_argument("--judge", help="the judge's model")
    setup.add_argument("--force", action="store_true", help="update an endpoint saved already")
    setup.add_argument("--no-models", action="store_true", help="do not download the spaCy models")

    endpoint = sub.add_parser("endpoint", help="list the saved endpoints, pick one, remove one")
    endpoint_sub = endpoint.add_subparsers(dest="endpoint_command", required=True)
    endpoint_sub.add_parser("list", help="the saved endpoints, the one in use marked")
    endpoint_use = endpoint_sub.add_parser("use", help="use this endpoint from now on")
    endpoint_remove = endpoint_sub.add_parser("remove", help="remove a saved endpoint")
    for p in (endpoint_use, endpoint_remove):
        p.add_argument("name")
        p.add_argument("--local", action="store_true", help="in ./leichtfacile.toml")

    settings = sub.add_parser("config", help="show, set, unset or edit the settings")
    settings_sub = settings.add_subparsers(dest="config_command", required=True)
    show = settings_sub.add_parser("show", help="every setting, its value and its source")
    show.add_argument(
        "--defaults", action="store_true", help="every setting with its default and meaning"
    )
    with_endpoint(show)
    config_path = settings_sub.add_parser("path", help="print the config file's path")
    config_set = settings_sub.add_parser("set", help="set a setting (section.key value)")
    config_set.add_argument("key", help="section.key, as `config show` lists them")
    config_set.add_argument("value", help='as TOML reads it (8001, true, ["understand"]) or text')
    config_unset = settings_sub.add_parser("unset", help="remove a setting from the file")
    config_unset.add_argument("key")
    config_edit = settings_sub.add_parser("edit", help="open the file in the editor")
    for p in (config_path, config_set, config_unset, config_edit):
        p.add_argument("--local", action="store_true", help="./leichtfacile.toml instead")

    models = sub.add_parser("models", help="download the spaCy models (German, French)")
    models.add_argument(
        "--from", dest="source", type=Path, help="a folder with the model wheels (offline)"
    )
    models.add_argument("--force", action="store_true", help="replace models already there")

    serve = sub.add_parser("serve", help="run the web application")
    serve.add_argument("--host", help="the interface (default: server.host, 127.0.0.1)")
    serve.add_argument("--port", type=int, help="the port (default: server.port, 8000)")
    serve.add_argument("--no-browser", action="store_true", help="do not open the browser")
    with_endpoint(serve)

    check_llm = sub.add_parser("check-llm", help="list models and make one short call")
    check_llm.add_argument("--model", help="model name (default: llm.models.writer)")
    check_llm.add_argument("--thinking", action="store_true", help="use thinking mode")
    with_endpoint(check_llm)

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
    simplify.add_argument("--condition", choices=list(CONDITIONS), default="P2")
    simplify.add_argument("--out", type=Path, default=Path("out"), help="output folder")
    simplify.add_argument("--writer", help="writer model (default: llm.models.writer)")
    simplify.add_argument(
        "--understand",
        help="model for the Understand stage (default: llm.models.understand, else the writer)",
    )
    simplify.add_argument("--judge", help="judge model (default: llm.models.judge)")
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
    with_endpoint(simplify)

    from leichtfacile.eval.cli import add_eval_parser

    add_eval_parser(sub)

    args = parser.parse_args(argv)
    if args.config:
        os.environ["LEICHTFACILE_CONFIG"] = str(args.config)
    use_overrides({
        "llm.endpoint": getattr(args, "endpoint", None),
        "llm.cache": True if getattr(args, "cache", False) else None,
        "server.host": getattr(args, "host", None),
        "server.port": getattr(args, "port", None),
    })  # fmt: skip
    try:
        return _dispatch(parser, args)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2


def with_endpoint(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--endpoint",
        help="an endpoint for this run, a preset or a saved one (default: llm.endpoint)",
    )


def _dispatch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.command == "setup":
        from leichtfacile.config import secret_value

        # `setup cscs` names a preset, `setup gpu --base-url ...` a new endpoint.
        preset = args.preset or (args.endpoint if args.endpoint in PRESETS else None)
        name = args.name or (None if args.endpoint in PRESETS else args.endpoint)
        try:
            code = configure.run_setup(
                preset=preset, name=name, base_url=args.base_url, api_key=args.api_key,
                api_key_env=args.api_key_env, model=args.model, judge=args.judge,
                force=args.force,
            )  # fmt: skip
            if code == 0 and not args.no_models:
                # Without a question asked so far, the models are not asked about either.
                variable = PRESETS[preset].values.get("api_key_env") if preset else None
                scripted = bool(
                    args.api_key or args.api_key_env or preset == "local"
                    or (variable and secret_value(variable))
                )  # fmt: skip
                code = offer_models(ask=None if scripted else input)
        except (EOFError, KeyboardInterrupt):
            print("\nSetup cancelled.", file=sys.stderr)
            return 1
        return code
    if args.command == "endpoint":
        return _endpoint(args)
    if args.command == "config":
        return _config(args)
    if args.command == "models":
        return _models(args.source, force=args.force)
    if args.command == "serve":
        # the app configures its logs (logs.py)
        return _serve(browser=not args.no_browser)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

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
    parser.error(f"unknown command {args.command}")
    return 2


def settings_or_exit() -> Settings:
    """The settings, or a short message instead of a traceback when they are
    incomplete or invalid."""
    from leichtfacile.config import get_settings

    try:
        return get_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from None


def _endpoint(args: argparse.Namespace) -> int:
    from leichtfacile.config import PROJECT_FILE, config_file

    if args.endpoint_command == "list":
        return configure.list_endpoints()
    path = PROJECT_FILE if args.local else config_file()
    if args.endpoint_command == "use":
        return configure.use_endpoint(args.name, path=path)
    return configure.remove_endpoint(args.name, path=path)


def _config(args: argparse.Namespace) -> int:
    from leichtfacile.config import PROJECT_FILE, config_file, reference_toml

    command = args.config_command
    if command == "show":
        if args.defaults:
            print(reference_toml(), end="")
            return 0
        return configure.show()
    path = PROJECT_FILE if args.local else config_file()
    if command == "path":
        print(path.resolve())
        return 0
    if command == "set":
        return configure.set_value(path, args.key, args.value)
    if command == "unset":
        return configure.unset_value(path, args.key)
    return configure.edit(path)


def _serve(*, browser: bool = True) -> int:
    import uvicorn

    # A missing setting stops here with a hint, not inside the server; so does a host
    # beyond this machine without a login (web/security.py).
    settings = settings_or_exit()
    models_or_exit()
    host, port = settings.server.host, settings.server.port
    if browser and settings.server.open_browser and wants_browser(host):
        address = f"[{host}]" if ":" in host else host
        open_when_ready(f"http://{address}:{port}/")
    # The app writes its own access line, with the request id and without the query
    # string (web/observability.py); uvicorn's would double it.
    uvicorn.run(
        "leichtfacile.web.app:create_app", factory=True, host=host, port=port, access_log=False
    )
    return 0


def models_or_exit() -> None:
    """Stop with a hint when the German or French spaCy model is missing: without them
    the checker would stop at the first German or French text."""
    from leichtfacile import spacy_models

    missing = spacy_models.missing()
    if missing:
        names = ", ".join(spacy_models.MODELS[lang].name for lang in missing)
        print(f"Missing the spaCy models {names}: run `leichtfacile models` (about 90 MB "
              "from GitHub), or `leichtfacile models --from <folder>` offline.",
              file=sys.stderr)  # fmt: skip
        raise SystemExit(2)


def offer_models(ask: Callable[[str], str] | None = input) -> int:
    """After setup: download the missing models, after asking (`ask` None: without)."""
    from leichtfacile import spacy_models

    missing = spacy_models.missing()
    if not missing:
        return 0
    size = sum(spacy_models.MODELS[lang].size for lang in missing) / 1e6
    if ask is not None:
        prompt = f"Download the language models for the checker now ({size:.0f} MB)? [Y/n] "
        if ask(prompt).strip().lower() in ("n", "no"):
            print("Later: `leichtfacile models`.")
            return 0
    return _models(None, force=False)


def _models(source: Path | None, *, force: bool) -> int:
    from leichtfacile import spacy_models

    langs = list(spacy_models.MODELS) if force else spacy_models.missing()
    for lang in spacy_models.MODELS:
        if lang not in langs:
            found = spacy_models.locate(lang)
            print(f"{spacy_models.MODELS[lang].name}: {found} (already there)")
    try:
        spacy_models.install(langs, source=source)
    except (OSError, ValueError) as exc:
        print(f"The models could not be installed: {exc}", file=sys.stderr)
        return 1
    return 0


def wants_browser(host: str) -> bool:
    """Open the browser only for a server on this machine, and on Linux only with a
    desktop: elsewhere Python would start a text browser in the terminal."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        return False
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def open_when_ready(url: str, timeout_s: float = 60.0) -> None:
    """Open `url` in the default browser as soon as its /healthz answers, from a thread,
    so that the server starts meanwhile; nothing happens if it never answers."""
    import threading
    import time
    import urllib.request
    import webbrowser

    def wait() -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(url + "healthz", timeout=2).close()
            except OSError:
                time.sleep(0.5)
                continue
            webbrowser.open(url)
            return

    threading.Thread(target=wait, name="open-browser", daemon=True).start()


def _check_llm(model: str | None, thinking: bool) -> int:
    from leichtfacile.config import listed
    from leichtfacile.llm.client import LLMClient, LLMError

    settings = settings_or_exit()
    client = LLMClient(settings)
    name, extra = client.resolve_model(model, thinking)
    print(
        f"endpoint:  {settings.llm.url}"
        + (f" ({settings.llm.endpoint})" if settings.llm.endpoint else "")
    )
    print(f"model:     {name} {extra or ''}".rstrip())

    try:
        models = client.list_models()
        print(f"listed:    {len(models)} models; requested model listed: {listed(name, models)}")
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
        # The operator's own URL: the private-network check is for the web form.
        doc = ingest.ingest_url(path_or_url, lang=lang, allow_private=True)
    else:
        doc = ingest.ingest_file(Path(path_or_url), lang=lang)
    if section:
        doc = ingest.select_section(doc, section)
    return doc


def _ingest(args: argparse.Namespace) -> int:
    from leichtfacile.ingest.errors import IngestError

    try:
        doc = load_source(args.input, args.lang, args.section)
    except (IngestError, OSError, ValueError) as exc:  # ValueError: a blank --section
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

    models_or_exit()
    try:
        doc = load_source(args.input, args.lang, args.section)
    except (IngestError, OSError, ValueError) as exc:
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
    from leichtfacile.export.bundle import build_bundle
    from leichtfacile.export.docx import to_docx
    from leichtfacile.export.html import to_html
    from leichtfacile.export.markdown import to_markdown
    from leichtfacile.ingest.errors import IngestError
    from leichtfacile.llm.client import LLMClient
    from leichtfacile.pipeline.orchestrator import Orchestrator
    from leichtfacile.schemas import Draft, JobConfig, PipelineSummary
    from leichtfacile.store import Store

    settings = settings_or_exit()
    models_or_exit()
    try:
        source = load_source(args.input, args.lang)
    except (IngestError, OSError) as exc:
        print(f"cannot read {args.input}: {exc}", file=sys.stderr)
        return 1
    store = Store(settings.data.dir / "leichtfacile.sqlite")
    config = JobConfig(
        lang=source.lang,
        level=args.level,
        condition=args.condition,
        endpoint=args.endpoint,  # --endpoint: the job's record says where it ran
        writer_model=args.writer,
        understand_model=args.understand,
        judge_model=args.judge,
        use_judge=not args.no_judge,
        max_repair_rounds=0 if args.no_repair else settings.pipeline.repair_rounds,
        max_facts_rounds=0 if args.no_repair else settings.pipeline.facts_rounds,
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
        docx = to_docx(draft, title=job.title, notice=notice, summary=summary)
        (out / "draft.docx").write_bytes(docx)
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
