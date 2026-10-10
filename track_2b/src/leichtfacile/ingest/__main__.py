"""Manual check: python -m leichtfacile.ingest <file|url> [--lang de] [--section QUERY] [--json]."""

from __future__ import annotations

import argparse
import logging
import sys

from leichtfacile.ingest import IngestError, ingest_file, ingest_url, select_section
from leichtfacile.schemas import LANGS

_MARKERS = {"paragraph": "p", "list_item": "li", "table_cell": "td"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m leichtfacile.ingest",
        description="Print the segments of a file or URL as the pipeline sees them.",
    )
    parser.add_argument("source", help="a .txt, .md, .html, .htm or .pdf file, or an http(s) URL")
    parser.add_argument("--lang", choices=LANGS, help="language (default: detected)")
    parser.add_argument("--section", help="keep the section under the first matching heading")
    parser.add_argument("--json", action="store_true", help="print the SourceDocument as JSON")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    try:
        if args.source.startswith(("http://", "https://")):
            doc = ingest_url(args.source, lang=args.lang, allow_private=True)
        else:
            doc = ingest_file(args.source, lang=args.lang)
        if args.section:
            doc = select_section(doc, args.section)
    except (IngestError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(doc.model_dump_json(indent=2))
        return 0
    print(
        f"id={doc.id} lang={doc.lang} title={doc.title!r} "
        f"segments={len(doc.segments)} words={doc.word_count()}"
    )
    for segment in doc.segments:
        marker = (
            f"h{segment.heading_level}" if segment.kind == "heading" else _MARKERS[segment.kind]
        )
        page = f" p{segment.page}" if segment.page else ""
        indent = "  " * len(segment.heading_path)
        print(f"{segment.id} {marker:<3}{segment.para:>4}{page} {indent}{segment.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
