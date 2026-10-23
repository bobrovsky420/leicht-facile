"""Fixtures of the web tests: the application on a scratch store against the fake
endpoint (`app_env`), shared by test_web.py and test_check.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from leichtfacile.llm.client import LLMClient
from leichtfacile.store import Store
from leichtfacile.web.app import create_app
from tests.conftest import FakeEndpoint, make_settings


@pytest.fixture
def app_env(tmp_path, endpoint: FakeEndpoint, sleeps):
    settings = make_settings(data_dir=tmp_path, llm_max_retries=0)
    llm = LLMClient(settings, http_client=endpoint.http_client(), sleep=sleeps.append)
    store = Store(tmp_path / "web.sqlite")
    app = create_app(settings, llm, store)
    with TestClient(app) as client:
        yield client, app, endpoint
    store.close()
