"""Command line: `python -m leichtfacile <command>`.

Commands so far:
- `serve`      run the web application
- `check-llm`  list the endpoint's models and make one short call
"""

from __future__ import annotations

import argparse
import logging
import sys

from leichtfacile import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leichtfacile", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    check = sub.add_parser("check-llm", help="list models and make one short call")
    check.add_argument("--model", help="model name (default: LLM_NAME)")
    check.add_argument("--thinking", action="store_true", help="use thinking mode")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "check-llm":
        return _check_llm(args.model, args.thinking)
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


if __name__ == "__main__":
    raise SystemExit(main())
