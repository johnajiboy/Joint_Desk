import io
import json
import shutil

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend import services as S
from backend.db import ROOT, Decision, get_engine
from kneedss.extract import Extraction

LETTERS = ROOT / "data" / "output" / "letters"
needs_cbc = pytest.mark.skipif(not shutil.which("cbc"), reason="needs the cbc solver (brew install cbc)")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("DATABASE_URL", f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}")
    mp.setenv("DEMO_MODE", "1")
    from backend.main import app
    with TestClient(app) as c:
        yield c
    mp.undo()


def upload(client, *files):
    return client.post("/letters", files=[("files", f) for f in files])


def letter_only_patient(client):
    """A waiting-list patient who has no letter."""
    with_letters = {r["id"] for r in client.get("/queue").json()}
    return next(f"KP{i:05d}" for i in range(1, 1501) if f"KP{i:05d}" not in with_letters)


# ---------------------------------------------------------------- reads

def test_health_reports_demo_mode(client):
    assert client.get("/health").json() == {"ok": True, "demo_mode": True}


def test_queue_is_the_250_referrals_by_priority(client):
    q = client.get("/queue").json()
    assert len(q) == 250 and {r["set"] for r in q} == {"dev", "test"}
    assert [r["priority"] for r in q] == sorted((r["priority"] for r in q), reverse=True)
    assert set(q[0]) >= {"id", "letter_id", "name", "pathway", "priority", "weeks_waiting", "decision"}


def test_queue_filters_by_pathway(client):
    surgery = client.get("/queue", params={"pathway": "surgery"}).json()
    both = client.get("/queue", params=[("pathway", "physio"), ("pathway", "weight_physio")]).json()
    assert surgery and all(r["pathway"] == "surgery" for r in surgery if not r["decision"])
    assert {r["pathway"] for r in both} <= {"physio", "weight_physio"}
    assert client.get("/queue", params={"pathway": "nonsense"}).status_code == 422


def test_patient_with_a_letter(client):
    p = client.get("/patients/KP00678").json()
    assert p["name"] == "Carol Lowe" and p["letter_id"] == "L0104" and p["letter_text"]
    assert p["spans"] and all(p["letter_text"][s["start"]:s["end"]] for s in p["spans"])
    assert sum(p["priority_parts"].values()) > 0 and p["label"]


def test_patient_without_a_letter(client):
    p = client.get(f"/patients/{letter_only_patient(client)}").json()
    assert p["letter_id"] is None and p["letter_text"] == "" and p["spans"] == [] and p["on_waiting_list"]


def test_unknown_or_bad_patient_id(client):
    assert client.get("/patients/KP99999").status_code == 404
    assert client.get("/patients/..%2F..%2Fetc").status_code in (404, 422)


def test_results_come_from_the_eval_files(client):
    r = client.get("/results").json()
    assert set(r) == {"extraction", "cleaning", "decision_tree", "optimise"}
    demo = json.loads((ROOT / "frontend" / "public" / "demo" / "results.json").read_text())
    assert r == demo                                                  # the API and the static demo agree


# ---------------------------------------------------------------- uploads

def test_known_letter_is_matched_to_its_patient_without_extraction(client, monkeypatch):
    monkeypatch.setattr(S.X, "extract", lambda *a, **k: pytest.fail("should reuse the stored result"))
    before = len(client.get("/queue").json())
    text = (LETTERS / "L0001.txt").read_bytes()
    [r] = upload(client, ("referral from GP.txt", text, "text/plain")).json()
    assert r["ok"] and r["referral"]["id"] == "KP00173" and r["referral"]["letter_id"] == "L0001"
    assert len(client.get("/queue").json()) == before


def test_docx_letter_is_read(client, monkeypatch):
    doc = Document()
    for line in (LETTERS / "L0002.txt").read_text().splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    monkeypatch.setattr(S.X, "extract", lambda *a, **k: pytest.fail("should reuse the stored result"))
    [r] = upload(client, ("L0002.docx", buf.getvalue(), "application/octet-stream")).json()
    # the DOCX text is the same letter once spacing is ignored, so it is recognised without a new read
    assert r["ok"] and r["referral"]["letter_id"] == "L0002" and r["referral"]["id"] == "KP00298"


def test_unknown_letter_in_demo_mode(client):
    [r] = upload(client, ("new.txt", b"Dear colleague, a brand new letter. NHS No: 999 000 0000", "text/plain")).json()
    assert r == {"file": "new.txt", "ok": False, "message": "Couldn't read file · demo mode"}


@pytest.mark.parametrize("name,data,message", [
    ("letter.exe", b"MZ", "Only PDF, DOCX or TXT"),
    ("letter.pdf", b"not a pdf", "Not a real PDF file"),
    ("letter.docx", b"not a zip", "Not a real DOCX file"),
    ("letter.txt", b"\xff\xfe\x00bad", "Text file is not UTF-8"),
    ("letter.txt", b"", "Empty file"),
    ("letter.txt", b"x" * (2 * 1024 * 1024 + 1), "File too large (max 2 MB)"),
])
def test_file_checks(client, name, data, message):
    [r] = upload(client, (name, data, "application/octet-stream")).json()
    assert r == {"file": name, "ok": False, "message": message}


def test_many_files_each_get_a_result(client):
    good = (LETTERS / "L0003.txt").read_bytes()
    res = upload(client, ("L0003.txt", good, "text/plain"), ("bad.exe", b"MZ", "x/y")).json()
    assert [r["ok"] for r in res] == [True, False]
    too_many = [("files", (f"{i}.txt", b"x", "text/plain")) for i in range(21)]
    assert client.post("/letters", files=too_many).status_code == 413


def test_new_nhs_number_creates_a_patient(client, monkeypatch):
    facts = {k: None for k in ["nhs_number", "name", "age", "sex", "side", "oks", "oks_before", "kl", "physio_weeks",
                               "bmi", "night_pain", "lives_alone_or_carer", "weeks_waiting"]}
    facts |= {"nhs_number": "999 123 4560", "name": "Test Person", "oks": 15, "oks_before": 18, "kl": 4,
              "physio_weeks": 8, "bmi": 30.0, "weeks_waiting": 3}
    monkeypatch.setattr(S.X, "extract", lambda text, lid, **k: Extraction(
        letter_id=lid, model="claude-test", facts=facts, quotes={"oks": "OKS 15"}, dropped=[], from_cache=True))
    [r] = upload(client, ("brand-new.txt", b"OKS 15. A letter nobody has seen before.", "text/plain")).json()
    assert r["ok"] and r["referral"]["id"] == "NEW234560" and r["referral"]["pathway"] == "surgery"
    p = client.get("/patients/NEW234560").json()
    assert p["on_waiting_list"] is False and p["name"] == "Test Person" and p["spans"][0]["field"] == "oks"
    assert any(q["id"] == "NEW234560" for q in client.get("/queue").json())


# ---------------------------------------------------------------- decisions

def test_confirm_records_who_when_and_pathway(client):
    d = client.post("/patients/KP00678/confirm", json={"by": "Dr Test", "reason": "Agree"}).json()
    assert d["kind"] == "confirmed" and d["by"] == "Dr Test" and d["reason"] == "Agree"
    assert d["pathway"] == d["old_pathway"] == d["was"] == "surgery" and d["at"]
    assert client.get("/patients/KP00678").json()["decision"]["kind"] == "confirmed"


def test_override_is_stored_with_old_and_new_and_changes_the_queue(client):
    pid = "KP00173"
    d = client.post(f"/patients/{pid}/override", json={"pathway": "surgery", "by": "Dr Test", "reason": "Severe pain"}).json()
    assert d["kind"] == "overridden" and d["old_pathway"] == "physio" and d["pathway"] == "surgery" and d["was"] == "physio"
    assert any(r["id"] == pid for r in client.get("/queue", params={"pathway": "surgery"}).json())
    back = client.post(f"/patients/{pid}/override", json={"pathway": "physio", "by": "Dr Test"}).json()
    assert back["kind"] == "confirmed" and back["old_pathway"] == "surgery"     # back to what the rules said
    with Session(get_engine()) as s:
        history = s.exec(select(Decision).where(Decision.patient_id == pid)).all()
    assert [(h.old_pathway, h.new_pathway) for h in history] == [("physio", "surgery"), ("surgery", "physio")]


def test_override_checks_its_input(client):
    assert client.post("/patients/KP00678/override", json={"pathway": "teleport"}).status_code == 422
    assert client.post("/patients/KP00678/override", json={"pathway": "physio", "reason": "x" * 501}).status_code == 422
    assert client.post("/patients/KP99999/override", json={"pathway": "physio"}).status_code == 404


# ---------------------------------------------------------------- week

@needs_cbc
def test_week_build_uses_overrides(client):
    plan = client.post("/week/build").json()
    assert plan["method"] == "optimiser" and [len(l["in"]) for l in plan["lists"]] == [12, 20, 8]
    first = plan["lists"][0]["in"][0]["id"]
    client.post(f"/patients/{first}/override", json={"pathway": "non_surgical", "by": "Dr Test", "reason": "Declined"})
    again = client.post("/week/build").json()
    assert all(p["id"] != first for l in again["lists"] for p in l["in"])


# ---------------------------------------------------------------- CORS

def test_cors_only_for_the_site_and_localhost(client):
    ok = client.options("/queue", headers={"Origin": "https://frontend-wine-ten-82.vercel.app",
                                           "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "https://frontend-wine-ten-82.vercel.app"
    local = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert local.headers.get("access-control-allow-origin") == "http://localhost:5173"
    other = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


# ---------------------------------------------------------------- PDF and DOCX uploads (stage 8)

def _export():
    import importlib.util
    spec = importlib.util.spec_from_file_location("export_pdfs", ROOT / "scripts" / "export_pdfs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FORMATS = [("L0010", "pdf"), ("L0020", "pdf"), ("L0030", "pdf"), ("T0010", "pdf"), ("T0020", "pdf"),
           ("L0040", "docx"), ("T0040", "docx")]


@pytest.mark.parametrize("lid,kind", FORMATS)
def test_pdf_and_docx_give_the_same_facts_and_pathway_as_the_txt(client, monkeypatch, lid, kind):
    P = _export()
    base = ROOT / "data" / "output" / ("test" if lid.startswith("T") else "")
    text = (base / "letters" / f"{lid}.txt").read_text()
    data = (P.letter_pdf if kind == "pdf" else P.letter_docx)(text, P.letter_meta(text))
    monkeypatch.setattr(S.X, "extract", lambda *a, **k: pytest.fail("no extraction: reuse the stored facts"))

    [txt] = upload(client, (f"{lid}.txt", text.encode(), "text/plain")).json()
    before = client.get(f"/patients/{txt['referral']['id']}").json()
    [doc] = upload(client, (f"{lid}.{kind}", data, "application/octet-stream")).json()
    after = client.get(f"/patients/{doc['referral']['id']}").json()

    assert txt["ok"] and doc["ok"] and doc["referral"]["id"] == txt["referral"]["id"]
    assert after["facts"] == before["facts"] and after["quotes"] == before["quotes"]
    assert (doc["referral"]["pathway"], doc["referral"]["priority"]) == (txt["referral"]["pathway"], txt["referral"]["priority"])
    assert after["letter_text"] != before["letter_text"]                 # the PDF/DOCX text, with its letterhead
    assert len(after["spans"]) == len(after["quotes"])                    # every quote highlighted in the new text
    assert all(after["letter_text"][s["start"]:s["end"]] for s in after["spans"])


def test_a_renamed_file_with_another_letter_inside_is_not_given_its_facts(client):
    P = _export()
    other = (ROOT / "data" / "output" / "letters" / "L0002.txt").read_text()
    pdf = P.letter_pdf(other, P.letter_meta(other))
    [r] = upload(client, ("L0001.pdf", pdf, "application/pdf")).json()
    # L0001's quotes are not in this document, so its stored facts are not reused, and the cache only holds
    # L0001's own text: in demo mode the file can't be read
    assert r == {"file": "L0001.pdf", "ok": False, "message": "Couldn't read file · demo mode"}
