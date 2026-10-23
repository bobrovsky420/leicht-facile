"""Write the settings reference into docs/configuration.md, between its markers, from
the settings' own descriptions (`config.reference_markdown`). tests/test_config.py
checks that the page is current.

    uv run python scripts/config_reference.py
"""

from __future__ import annotations

from pathlib import Path

from leichtfacile.config import reference_markdown

DOC = Path(__file__).resolve().parents[1] / "docs" / "configuration.md"
START, END = "<!-- reference:start -->\n", "<!-- reference:end -->"


def main() -> None:
    text = DOC.read_text(encoding="utf-8")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    reference = reference_markdown().strip()
    DOC.write_text(f"{head}{START}\n{reference}\n\n{END}{tail}", encoding="utf-8", newline="\n")
    print(f"{DOC}: reference written")


if __name__ == "__main__":
    main()
