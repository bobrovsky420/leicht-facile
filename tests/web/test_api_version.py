"""The JSON API lives under /api/v1 (docs/architecture.md §7): the prefix of 0.11 and
earlier answers the same, with the headers that announce its end, and stays outside the
schema; docs/openapi.json holds the API's description and stays equal to the code."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path

from leichtfacile.web import api
from leichtfacile.web.app import api_schema

ROOT = Path(__file__).resolve().parents[2]


def test_the_old_prefix_answers_with_deprecation_sunset_and_successor(app_env) -> None:
    client, _, _ = app_env
    current = client.get("/api/v1/jobs")
    legacy = client.get("/api/jobs")
    assert current.status_code == legacy.status_code == 200
    assert legacy.json() == current.json()
    deprecated_on = int(datetime(2026, 11, 3, tzinfo=UTC).timestamp())
    assert legacy.headers["Deprecation"] == f"@{deprecated_on}"
    assert legacy.headers["Sunset"] == format_datetime(api.LEGACY_SUNSET, usegmt=True)
    assert legacy.headers["Sunset"].startswith("Mon, 03 May 2027")
    assert legacy.headers["Link"] == '</api/v1/jobs>; rel="successor-version"'
    for name in ("Deprecation", "Sunset", "Link"):
        assert name not in current.headers
    # A refusal under the old prefix says so too; the current prefix is never "legacy".
    missing = client.get("/api/jobs/nope")
    assert missing.status_code == 404
    assert missing.headers["Link"] == '</api/v1/jobs/nope>; rel="successor-version"'
    assert api.is_legacy("/api/jobs") and api.is_legacy("/api/jobs/x/export")
    assert not api.is_legacy("/api/v1/jobs") and not api.is_legacy("/apix/jobs")


def test_the_schema_describes_the_api_under_its_prefix_and_the_file_is_current(app_env) -> None:
    _, app, _ = app_env
    schema = api_schema()
    paths = schema["paths"]
    assert paths and all(path.startswith("/api/v1/") for path in paths)
    assert schema["info"]["version"] == "1"  # the API's version, not the app's
    served = app.openapi()["paths"]
    assert {path: spec for path, spec in served.items() if path.startswith("/api/")} == paths
    assert not any(api.is_legacy(path) for path in served), "the old prefix is outside"
    snapshot = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    assert snapshot == schema, "run `uv run python scripts/openapi.py`"
