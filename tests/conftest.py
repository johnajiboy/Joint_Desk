"""Tests never call the API or touch a hosted database.

Blank values (not missing ones) stop load_dotenv() from filling them in from .env: no API key, no DATABASE_URL
(so the backend uses a local SQLite file or the throwaway Postgres a test starts), no upload passcode."""
import os

import pytest
from fastapi.testclient import TestClient

for key in ("ANTHROPIC_API_KEY", "DATABASE_URL", "UPLOAD_PASSCODE"):
    os.environ[key] = ""


@pytest.fixture(autouse=True)
def no_api_calls(monkeypatch):
    from kneedss import llm

    def refuse():
        raise AssertionError("a test tried to call the Anthropic API")
    monkeypatch.setattr(llm, "_client", refuse)


@pytest.fixture(scope="module", params=["sqlite", "postgres"])
def client(request, tmp_path_factory):
    """The whole API on SQLite and on a throwaway local Postgres (pgserver; skipped if it isn't installed)."""
    mp = pytest.MonkeyPatch()
    server = None
    if request.param == "sqlite":
        mp.setenv("DATABASE_URL", f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}")
    else:
        pgserver = pytest.importorskip("pgserver")
        server = pgserver.get_server(tmp_path_factory.mktemp("pg"), cleanup_mode="stop")
        mp.setenv("DATABASE_URL", server.get_uri())
    mp.setenv("DEMO_MODE", "1")
    from backend.main import app
    with TestClient(app) as c:
        yield c
    mp.undo()
    if server is not None:
        server.cleanup()
