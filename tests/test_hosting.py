"""Hosting: the SQLite/Postgres switch, the upload passcode, the daily LLM cap and the upload limits.
No API calls: extraction is faked (and conftest.py makes any real call fail)."""
import io

import pytest
from openpyxl import Workbook

from backend import db
from backend import main as M
from backend import services as S
from kneedss.extract import Extraction

FACTS = {k: None for k in ["nhs_number", "name", "age", "sex", "side", "oks", "oks_before", "kl", "physio_weeks",
                           "bmi", "night_pain", "lives_alone_or_carer", "weeks_waiting"]}
FACTS |= {"nhs_number": "999 765 4329", "name": "Cap Test", "oks": 20, "kl": 3, "physio_weeks": 12, "bmi": 28.0}


# ---------------------------------------------------------------- SQLite / Postgres switch

@pytest.mark.parametrize("given, expected", [
    ("", f"sqlite:///{db.DEFAULT_DB}"),
    ("   ", f"sqlite:///{db.DEFAULT_DB}"),
    ("postgres://u:pw@db.example.supabase.co:5432/postgres", "postgresql+psycopg://u:pw@db.example.supabase.co:5432/postgres"),
    ("postgresql://u:pw@pooler.supabase.com:6543/postgres?sslmode=require",
     "postgresql+psycopg://u:pw@pooler.supabase.com:6543/postgres?sslmode=require"),
    ("postgresql+psycopg://u:pw@h/db", "postgresql+psycopg://u:pw@h/db"),
    ("sqlite:////tmp/x.db", "sqlite:////tmp/x.db"),
])
def test_database_url_picks_postgres_when_set_else_sqlite(monkeypatch, given, expected):
    monkeypatch.setenv("DATABASE_URL", given)
    assert db.database_url() == expected
    assert db.backend_name() == ("postgres" if expected.startswith("postgresql") else "sqlite")


def test_engine_options_per_database():
    assert db.engine_options("sqlite:///x.db") == {"connect_args": {"check_same_thread": False}}
    pg = db.engine_options("postgresql+psycopg://u:pw@h/db")
    assert pg["connect_args"] == {"prepare_threshold": None, "connect_timeout": 10} and pg["pool_pre_ping"]   # pooler-safe, fails fast


def test_health_and_startup_never_show_the_database_url(client, capsys, caplog):
    url = db.database_url()
    body = client.get("/health").text
    assert db.backend_name() in body and url not in body and "sqlite:///" not in body and "postgresql" not in body
    out = capsys.readouterr()
    assert url not in out.out + out.err + caplog.text


def test_seeds_only_when_empty(client):
    from sqlmodel import Session, func, select
    with Session(db.get_engine()) as s:
        before = s.exec(select(func.count()).select_from(db.Patient)).one()
    db.init_db()                                            # a restart: tables are full, nothing is added
    with Session(db.get_engine()) as s:
        assert s.exec(select(func.count()).select_from(db.Patient)).one() == before == 1500


# ---------------------------------------------------------------- passcode

@pytest.fixture
def passcode(monkeypatch):
    monkeypatch.setenv("UPLOAD_PASSCODE", "knee-2026")

    async def no_wait(_):
        return None
    monkeypatch.setattr(M.asyncio, "sleep", no_wait)
    return "knee-2026"


def xlsx() -> bytes:
    wb = Workbook()
    wb.active.append(["NHS No", "Patient name"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_uploads_and_imports_need_the_passcode(client, passcode):
    letter = [("files", ("a.txt", b"Dear GP", "text/plain"))]
    sheet = {"file": ("s.xlsx", xlsx(), "application/octet-stream")}
    for headers in ({}, {"X-Upload-Passcode": "wrong"}):
        assert client.post("/letters", files=letter, headers=headers).status_code == 401
        assert client.post("/import/preview", files=sheet, headers=headers).status_code == 401
        assert client.post("/import/commit", files=sheet, data={"mapping": "{}"}, headers=headers).status_code == 401
    ok = {"X-Upload-Passcode": passcode}
    assert client.post("/letters", files=letter, headers=ok).status_code == 200
    assert client.post("/import/preview", files=sheet, headers=ok).status_code == 200
    assert client.get("/health").json()["passcode"] is True
    assert client.get("/queue").status_code == 200                 # reading stays open


def test_passcode_check_for_the_app(client, passcode):
    assert client.post("/passcode", json={"passcode": passcode}).json() == {"ok": True}
    assert client.post("/passcode", json={"passcode": "nope"}).status_code == 401


def test_no_passcode_set_means_open_for_local_use(client):
    assert client.post("/passcode", json={"passcode": ""}).status_code == 200
    assert client.post("/letters", files=[("files", ("a.txt", b"Dear GP", "text/plain"))]).status_code == 200


# ---------------------------------------------------------------- daily cap

@pytest.fixture
def live_reads(monkeypatch):
    """DEMO_MODE off with a cap of 2 and a fake reader that counts its calls (no API)."""
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("LLM_DAILY_CAP", "2")
    monkeypatch.setattr(S, "today", lambda: "2026-10-22")
    calls = []

    def fake_extract(text, lid, **k):
        calls.append(lid)
        return Extraction(letter_id=lid, model="claude-test", facts=FACTS, quotes={"oks": "OKS 20"}, dropped=[],
                          from_cache=False)
    monkeypatch.setattr(S.X, "extract", fake_extract)
    monkeypatch.setattr(S.X, "is_cached", lambda text, lid: False)
    return calls


def send(client, name: str, text: str) -> dict:
    [r] = client.post("/letters", files=[("files", (name, text.encode(), "text/plain"))]).json()
    return r


def test_daily_cap_stops_new_reads_and_cached_letters_never_count(client, live_reads, monkeypatch):
    assert send(client, "one.txt", "OKS 20. Letter one for the cap.")["ok"]
    assert send(client, "two.txt", "OKS 20. Letter two for the cap.")["ok"]
    third = send(client, "three.txt", "OKS 20. Letter three for the cap.")
    assert third == {"file": "three.txt", "ok": False, "message": "Daily limit reached · try tomorrow"}
    assert len(live_reads) == 2                                     # the third never reached the reader
    assert client.get("/health").json()["llm_reads_today"] == 2

    assert send(client, "one again.txt", "OKS 20. Letter one for the cap.")["ok"]        # already read: free
    monkeypatch.setattr(S.X, "is_cached", lambda text, lid: True)
    assert send(client, "cached.txt", "OKS 20. A letter with a saved answer.")["ok"]     # saved answer: free
    assert len(live_reads) == 3 and client.get("/health").json()["llm_reads_today"] == 2

    monkeypatch.setattr(S.X, "is_cached", lambda text, lid: False)
    monkeypatch.setattr(S, "today", lambda: "2026-10-23")          # a new day, a new count
    assert send(client, "three.txt", "OKS 20. Letter three for the cap.")["ok"]


def test_demo_mode_never_reserves_a_read(client, monkeypatch):
    monkeypatch.setenv("LLM_DAILY_CAP", "0")
    r = send(client, "unknown.txt", "A letter nobody has a saved answer for.")
    assert r["message"] == "Couldn't read file · demo mode"         # not the daily limit: nothing was spent


def test_reserve_takes_exactly_the_cap(client, monkeypatch):
    from sqlmodel import Session
    monkeypatch.setenv("LLM_DAILY_CAP", "3")
    monkeypatch.setattr(S, "today", lambda: "2026-11-01")
    with Session(db.get_engine()) as s:
        assert [S.reserve_llm_read(s) for _ in range(5)] == [True, True, True, False, False]
        assert S.reads_today(s) == 3


# ---------------------------------------------------------------- upload limits

def test_at_most_five_files_of_two_mb(client):
    six = [("files", (f"{i}.txt", b"Dear GP", "text/plain")) for i in range(6)]
    assert client.post("/letters", files=six).status_code == 413
    [big] = client.post("/letters", files=[("files", ("big.txt", b"a" * (2 * 1024 * 1024 + 1), "text/plain"))]).json()
    assert big == {"file": "big.txt", "ok": False, "message": "File too large (max 2 MB)"}
