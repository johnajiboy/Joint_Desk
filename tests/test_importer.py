import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from kneedss import importer as I
from kneedss.clean import ROOT

SAMPLE = ROOT / "data" / "samples"


def detected(*headers):
    return {c["header"]: (c["field"], c["confidence"]) for c in I.detect(list(headers))}


# ---------------------------------------------------------------- header detection

def test_exact_names_and_aliases():
    d = detected("nhs_number", "Patient name", "DOB", "Oxford score", "X-ray grade", "Kellgren-Lawrence", "BMI (kg/m2)",
                 "NHS No")
    assert d["nhs_number"] == ("nhs_number", "exact")
    assert d["Patient name"] == ("name", "alias") and d["DOB"] == ("date_of_birth", "alias")
    assert d["Oxford score"] == ("oks", "alias") and d["X-ray grade"] == ("kl_grade", "alias")
    assert d["Kellgren-Lawrence"] == (None, "none")           # KL already went to "X-ray grade": one column per field
    assert d["BMI (kg/m2)"] == ("bmi", "alias")
    assert d["NHS No"] == (None, "none")                      # the exact column wins, one column per field


@pytest.mark.parametrize("header,field", [("NHS No.", "nhs_number"), ("nhs number", "nhs_number"), ("NHSNumber", "nhs_number"),
                                          ("knee score", "oks"), ("KL", "kl_grade"), ("xray grade", "kl_grade")])
def test_aliases_ignore_case_spaces_and_punctuation(header, field):
    assert I.detect([header])[0] == {"header": header, "field": field, "confidence": "alias" if I.norm(header) != I.norm(field) else "exact"}


def test_fuzzy_and_unknown():
    d = detected("Refferal date", "Date of brith", "Notes", "Favourite colour")
    assert d["Refferal date"] == ("referral_date", "fuzzy") and d["Date of brith"] == ("date_of_birth", "fuzzy")
    assert d["Notes"] == (None, "none") and d["Favourite colour"] == (None, "none")


def test_mapping_problems_block_missing_required_and_duplicates():
    assert I.mapping_problems({"a": "nhs_number", "b": "name", "c": "date_of_birth"}) == ["Missing: Referral date"]
    assert "Two columns for Name" in I.mapping_problems({"a": "nhs_number", "b": "name", "c": "name", "d": "date_of_birth", "e": "referral_date"})


# ---------------------------------------------------------------- one row

GOOD = {"nhs_number": "999 000 0018", "name": "Jane  Example", "date_of_birth": "14/03/1956", "referral_date": "2026-05-02",
        "sex": "F", "side": "Rt", "oks": "22", "oks_before": "26", "kl_grade": "3", "bmi": "31.4", "physio_weeks": "8",
        "injections": "1", "night_pain": "Y", "lives_alone_or_carer": "no", "walking_aid": "", "diabetes": "No",
        "smoking_status": "ex-smoker", "practice_code": "y99001"}


def test_clean_row_standardises_labels():
    r = I.clean_row(GOOD)
    assert r["nhs_number"] == "999 000 0018" and r["name"] == "Jane Example" and r["date_of_birth"] == "1956-03-14"
    assert (r["sex"], r["side"], r["smoking_status"], r["practice_code"]) == ("Female", "Right", "Ex-smoker", "Y99001")
    assert (r["oks"], r["kl_grade"], r["bmi"]) == (22, 3, 31.4)
    assert (r["night_pain"], r["lives_alone_or_carer"], r["walking_aid"], r["diabetes"]) == (True, False, None, False)
    assert r["age"] == 70 and r["weeks_waiting"] == 24                     # on the extract date, 20/10/2026


def test_missing_optional_values_stay_empty_and_the_rules_ask_the_gp():
    r = I.clean_row({**GOOD, "oks": "", "kl_grade": ""})
    assert r["oks"] is None and I.classify(r)["pathway"] == "review"


@pytest.mark.parametrize("change,reason", [
    ({"nhs_number": "999 000 0019"}, "fails the check"),
    ({"name": ""}, "Name missing"),
    ({"oks": "52"}, "outside 0-48"),
    ({"kl_grade": "5"}, "outside 0-4"),
    ({"bmi": "314"}, "outside 12-80"),
    ({"oks": "twenty"}, "is not a number"),
    ({"physio_weeks": "6.5"}, "whole number"),
    ({"date_of_birth": "31/02/1950"}, "is not a date"),
    ({"referral_date": "2027-01-01"}, "in the future"),
    ({"sex": "unknown"}, "Sex 'unknown' is not recognised"),
    ({"night_pain": "sometimes"}, "is not yes or no"),
    ({"practice_code": "ABC"}, "not an ODS code"),
])
def test_invalid_values_skip_the_row_with_a_reason(change, reason):
    with pytest.raises(ValueError, match=reason):
        I.clean_row({**GOOD, **change})


def test_classify_uses_the_rules():
    d = I.classify(I.clean_row(GOOD))
    assert d["pathway"] == "surgery" and d["rule"] == 4 and 0 <= d["priority"] <= 100
    assert d["facts"]["kl"] == 3 and d["facts"]["smoking"] == "Ex-smoker"


# ---------------------------------------------------------------- the sample files

@pytest.mark.parametrize("name", ["import_sample.csv", "import_sample.xlsx"])
def test_sample_has_three_bad_rows_skipped_with_reasons(name):
    p = I.preview(name, (SAMPLE / name).read_bytes())
    assert p["total_rows"] == 30 and p["valid"] == 27 and p["problems"] == [] and len(p["rows"]) == 10
    reasons = sorted(s["reason"] for s in p["skipped"])
    assert len(reasons) == 3
    assert any("fails the check" in r for r in reasons) and any("outside 0-48" in r for r in reasons) and any("is not a date" in r for r in reasons)
    fields = {c["header"]: c["field"] for c in p["columns"]}
    assert fields["NHS No"] == "nhs_number" and fields["Oxford score"] == "oks" and fields["X-ray grade"] == "kl_grade"
    assert fields["Refferal date"] == "referral_date" and fields["Notes"] is None


def test_repeated_nhs_number_in_one_file_is_skipped():
    headers = ["nhs_number", "name", "date_of_birth", "referral_date"]
    rows = [["999 000 0018", "A", "1950-01-01", "2026-01-01"], ["9990000018", "B", "1950-01-01", "2026-01-01"]]
    out = I.plan(headers, rows, {h: h for h in headers})
    assert len(out["valid"]) == 1 and out["skipped"][0]["reason"] == "NHS number repeated in this file"


def test_template_has_the_defined_headers_and_two_valid_rows():
    rows = list(csv.reader(io.StringIO(I.template_csv())))
    assert rows[0] == list(I.FIELDS) and len(rows) == 3
    assert I.plan(rows[0], rows[1:], {h: h for h in rows[0]})["skipped"] == []


# ---------------------------------------------------------------- API: update vs create

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("DATABASE_URL", f"sqlite:///{tmp_path_factory.mktemp('imp') / 'imp.db'}")
    mp.setenv("DEMO_MODE", "1")
    from backend.main import app
    with TestClient(app) as c:
        yield c
    mp.undo()


def sample_file(name="import_sample.csv"):
    return {"file": (name, (SAMPLE / name).read_bytes(), "application/octet-stream")}


def test_preview_endpoint(client):
    p = client.post("/import/preview", files=sample_file()).json()
    assert p["valid"] == 27 and len(p["rows"]) == 10 and {"field", "label", "required"} <= set(p["fields"][0])


def test_commit_updates_existing_and_creates_new_patients(client):
    from backend.db import ImportRecord, get_engine
    before = {r["id"] for r in client.get("/queue").json()}
    mapping = {c["header"]: c["field"] for c in client.post("/import/preview", files=sample_file()).json()["columns"]}
    r = client.post("/import/commit", files=sample_file(), data={"mapping": json.dumps(mapping), "by": "Dr Import"}).json()
    assert (r["added"], r["updated"], len(r["skipped"])) == (17, 10, 3)
    ids = {x["id"] for x in r["referrals"]}
    assert sum(i.startswith("IMP") for i in ids) == 17 and sum(i.startswith("KP") for i in ids) == 10
    queue = {x["id"]: x for x in client.get("/queue").json()}
    assert ids <= set(queue) and len(queue) == len(before | ids)
    new = next(x for x in r["referrals"] if x["id"].startswith("IMP"))
    assert queue[new["id"]]["set"] == "import" and queue[new["id"]]["filename"] == "import_sample.csv"
    with Session(get_engine()) as s:
        rec = s.exec(select(ImportRecord)).all()[-1]
    assert (rec.by, rec.filename, rec.added, rec.updated, rec.skipped, rec.rows) == ("Dr Import", "import_sample.csv", 17, 10, 3, 30)
    again = client.post("/import/commit", files=sample_file("import_sample.xlsx"), data={"mapping": json.dumps(mapping)}).json()
    assert (again["added"], again["updated"]) == (0, 27)                  # same patients the second time: all updates


def test_commit_blocks_a_mapping_without_required_fields(client):
    r = client.post("/import/commit", files=sample_file(), data={"mapping": json.dumps({"NHS No": "nhs_number"})})
    assert r.status_code == 422 and "Missing: Name" in r.json()["detail"]


@pytest.mark.parametrize("name,data,status", [
    ("x.txt", b"a,b", 415), ("x.xlsx", b"not a zip", 415), ("x.csv", b"\xff\xfe\x00", 415), ("x.csv", b"", 422),
    ("x.csv", b"a" * (5 * 1024 * 1024 + 1), 413),
])
def test_file_checks(client, name, data, status):
    assert client.post("/import/preview", files={"file": (name, data, "application/octet-stream")}).status_code == status


def test_bad_mapping_json(client):
    r = client.post("/import/preview", files=sample_file(), data={"mapping": json.dumps({"NHS No": "teleport"})})
    assert r.status_code == 422
