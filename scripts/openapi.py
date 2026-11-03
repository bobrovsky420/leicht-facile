"""Write the JSON API's OpenAPI description to docs/openapi.json (`web/app.api_schema`).
tests/web/test_api_version.py checks that the file is current.

    uv run python scripts/openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from leichtfacile.web.app import api_schema

DOC = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def main() -> None:
    text = json.dumps(api_schema(), indent=2, ensure_ascii=False) + "\n"
    DOC.write_text(text, encoding="utf-8", newline="\n")
    print(f"{DOC}: written")


if __name__ == "__main__":
    main()
