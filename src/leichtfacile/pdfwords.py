"""The words of a PDF's pages, read with pdfplumber, in a process of their own on request.

The one step of the ingest that a hostile file can make expensive: a compressed stream
of a few hundred kilobytes unpacks to gigabytes, and a thousand pages that share one
small stream take seconds (audit of 6 November 2026: a 195 kB upload peaked at 449 MB,
1000 pages from 159 kB took 4.2 s). Every read stops at `MAX_PAGES` before it parses a
page, and at `stop` characters of words when it is given. `read_isolated`, which the
web app uses for uploads and fetched pages, runs the read in a child process that ends
after `TIME_LIMIT_S` and may take `MEMORY_LIMIT` bytes of address space (POSIX; Windows
has no such limit), so one file cannot hold the service's memory or a thread for long.

The child is `python -m leichtfacile.pdfwords`: the file on its standard input, its
answer as JSON on its standard output. This module imports pdfplumber and nothing of
the app, so the child starts in about a second (the ingest package would bring spaCy
and trafilatura along); ingest/pdf.py builds the layout from what it returns.
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

import pdfplumber

log = logging.getLogger(__name__)

MAX_PAGES = 200
TIME_LIMIT_S = 60.0
MEMORY_LIMIT = 1_000_000_000  # bytes of the child's address space
SOFT_HYPHEN = "\N{SOFT HYPHEN}"

_MEMORY = (
    "reading the PDF needs more memory than one file may take (a compressed stream that "
    "unpacks to far more than the file's size?)"
)

# text, x0, x1, top, bottom, size, font name
Word = tuple[str, float, float, float, float, float, str]


@dataclass(frozen=True)
class Page:
    number: int
    width: float
    height: float
    words: list[Word]
    pictured: float = 0.0  # of a page without words: the share under images and fills


class Refused(Exception):
    """The PDF cannot be read, or not within the limits; the message says why (ingest/pdf.py
    raises it as an `ExtractionError`)."""


class TooLong(Exception):
    """The words read so far add up to more than `stop` characters (`chars`; ingest/pdf.py
    raises it as a `DocumentTooLongError`)."""

    def __init__(self, chars: int) -> None:
        super().__init__(chars)  # the arguments as given, so that it pickles
        self.chars = chars


def hyphens_of_text_layer(text: str) -> str:
    """A soft hyphen in a PDF's text layer is a drawn hyphen: InDesign and Word map the
    hyphen glyph to U+00AD, so the normaliser, which drops soft hyphens as invisible,
    read the DRV brochure's Martin-Luther-Straße 2-4 as MartinLutherStraße 24 and its
    Telefon 06232 17-0 as 170 (30 October 2026). As a plain hyphen it goes through the
    line-end dehyphenation of `join_lines` like any other."""
    return text.replace(SOFT_HYPHEN, "-")


def read(
    data: bytes, stop: int | None = None, max_pages: int = MAX_PAGES
) -> tuple[str | None, list[Page]]:
    """The metadata title and the pages with their upright words, in this process."""
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:  # pdfminer raises many exception types for broken files
        raise Refused(f"not a readable PDF ({type(exc).__name__})") from exc
    with pdf:
        try:
            title = (pdf.metadata or {}).get("Title")
            pages = _pages(pdf, stop, max_pages)
        except (Refused, TooLong, MemoryError):
            raise
        except Exception as exc:
            if _out_of_memory(exc):
                raise Refused(_MEMORY) from exc
            raise Refused(f"the PDF could not be read ({type(exc).__name__})") from exc
    return (title if isinstance(title, str) else None), pages


def _out_of_memory(exc: BaseException | None) -> bool:
    """Whether the error is, or wraps, a `MemoryError`: pdfplumber raises pdfminer's
    errors as its `PdfminerException`, the memory limit's among them."""
    for _ in range(10):  # at most ten links, should a chain point back at itself
        if exc is None:
            return False
        if isinstance(exc, MemoryError) or any(isinstance(a, MemoryError) for a in exc.args):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def _pages(pdf: Any, stop: int | None, max_pages: int) -> list[Page]:
    if len(pdf.pages) > max_pages:
        raise Refused(
            f"the PDF has {len(pdf.pages)} pages; at most {max_pages} are read: split it into parts"
        )
    pages: list[Page] = []
    chars = 0
    for number, page in enumerate(pdf.pages, start=1):
        raw = page.extract_words(extra_attrs=["size", "fontname"])
        words = [
            (
                hyphens_of_text_layer(w["text"]),
                float(w["x0"]),
                float(w["x1"]),
                float(w["top"]),
                float(w["bottom"]),
                float(w["size"]),
                str(w["fontname"]),
            )
            for w in raw
            if w.get("upright", True) and w["text"].strip()
        ]
        chars += sum(len(word[0]) + 1 for word in words)
        if stop is not None and chars > stop:
            raise TooLong(chars)
        width, height = float(page.width), float(page.height)
        pictured = 0.0 if words else _pictured(page, width, height)
        pages.append(Page(number, width, height, words, pictured))
        page.close()  # pdfplumber keeps a page's objects until then
    return pages


def _pictured(page: Any, width: float, height: float) -> float:
    """The share of the page under images and filled shapes, their boxes clipped to it."""
    shapes = [o for o in (*page.rects, *page.curves) if o.get("fill")]
    area = 0.0
    for obj in (*page.images, *shapes):
        w = min(float(obj["x1"]), width) - max(float(obj["x0"]), 0.0)
        h = min(float(obj["bottom"]), height) - max(float(obj["top"]), 0.0)
        area += max(w, 0.0) * max(h, 0.0)
    return min(area / (width * height), 1.0) if width and height else 0.0


def read_isolated(
    data: bytes,
    stop: int | None = None,
    *,
    time_limit_s: float = TIME_LIMIT_S,
    memory_limit: int = MEMORY_LIMIT,
) -> tuple[str | None, list[Page]]:
    """`read` in a child process, ended after `time_limit_s`, its address space limited
    to `memory_limit` bytes where the system has such limits."""
    command = [sys.executable, "-m", __name__, str(stop or 0), str(memory_limit)]
    try:
        done = subprocess.run(  # noqa: S603  (this interpreter, this module, two numbers)
            command, input=data, capture_output=True, timeout=time_limit_s, check=False
        )
    except subprocess.TimeoutExpired:  # the child is killed by then
        raise Refused(f"the PDF took more than {time_limit_s:.0f} s to read") from None
    if done.returncode != 0:
        # The exception's name from the traceback's last line, not its message, which
        # could quote the document.
        last = done.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
        name = last[0].split(":", 1)[0][:80] if last else ""
        log.warning("the PDF reader ended with %s (%s)", done.returncode, name)
        raise Refused(_MEMORY if done.returncode < 0 else "the PDF could not be read")
    try:
        answer = json.loads(done.stdout)
    except ValueError:  # no answer written (the child is ours: it always writes one)
        raise Refused("the PDF could not be read") from None
    if "too_long" in answer:
        raise TooLong(answer["too_long"])
    if "refused" in answer:
        raise Refused(answer["refused"])
    pages = [
        Page(number, width, height, [tuple(w) for w in words], pictured)
        for number, width, height, words, pictured in answer["pages"]
    ]
    return answer["title"], pages


def _main() -> None:
    """The child: limits, then the file from standard input, the answer to standard
    output."""
    stop, memory_limit = (int(arg) for arg in sys.argv[1:3])
    _limit_memory(memory_limit)
    answer: dict[str, Any]
    try:
        title, pages = read(sys.stdin.buffer.read(), stop or None)
        answer = {
            "title": title,
            "pages": [[p.number, p.width, p.height, p.words, p.pictured] for p in pages],
        }
    except TooLong as exc:
        answer = {"too_long": exc.chars}
    except Refused as exc:
        answer = {"refused": str(exc)}
    except MemoryError:
        answer = {"refused": _MEMORY}
    sys.stdout.write(json.dumps(answer))


def _limit_memory(limit: int) -> None:
    if sys.platform == "win32":  # no limit on the address space there
        return
    import resource

    # macOS refuses the limit, and a lower one set already stays: the time limit holds.
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


if __name__ == "__main__":
    _main()
