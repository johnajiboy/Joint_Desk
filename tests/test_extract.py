import io
import json

import pytest
from docx import Document

from kneedss import extract as X
from kneedss import llm
from kneedss.schemas import FIELDS, LetterFacts

LETTER = """Patient: Ms Aisha HALL     DOB: 28/06/1954
NHS No: 999 809 9129
  BMI 25.4 kg/m2 (17/12/2025)
Her Oxford Knee Score today is 22 (previously 24). Sleeps well.
X-ray: Moderate osteophytes with definite joint space narrowing, KL3.
She has completed five weeks of physiotherapy.
"""


def raw(**facts):
    """A full LLM answer: every field null except the ones given as (value, quote)."""
    out = {f: {"value": None, "quote": None} for f in FIELDS}
    for f, (v, q) in facts.items():
        out[f] = {"value": v, "quote": q}
    return out


GOOD = raw(
    nhs_number=("999 809 9129", "999 809 9129"),
    oks=(22, "Oxford Knee Score today is 22"),
    oks_before=(24, "(previously 24)"),
    kl=(3, "KL3"),
    physio_weeks=(5, "five weeks of physiotherapy"),
    bmi=(25.4, "BMI 25.4 kg/m2 (17/12/2025)"),
    night_pain=(False, "Sleeps well"),
    diabetes=(False, None),
)


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(X, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(X, "load_dotenv", lambda: None)
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("CLAUDE_MODEL", "claude-test")
    return tmp_path


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def complete_json(system, prompt, schema):
        calls.append(prompt)
        return GOOD
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return calls


# ---------------------------------------------------------------- schema

def test_schema_is_strict_ready():
    schema = llm.transform_schema(LetterFacts.model_json_schema())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(FIELDS)
    for name, sub in schema["$defs"].items():
        assert sub["additionalProperties"] is False, name
        assert set(sub["required"]) == {"value", "quote"}, name


# ---------------------------------------------------------------- quote check

def test_quote_check_keeps_quoted_facts():
    facts, quotes, dropped = X.check_quotes(GOOD, LETTER)
    assert dropped == []
    assert facts["oks"] == 22 and facts["kl"] == 3 and facts["night_pain"] is False
    assert quotes["bmi"] == "BMI 25.4 kg/m2 (17/12/2025)"


def test_quote_check_drops_made_up_quote():
    facts, _, dropped = X.check_quotes(raw(oks=(19, "OKS 19/48")), LETTER)
    assert facts["oks"] is None
    assert dropped == [{"field": "oks", "value": 19, "quote": "OKS 19/48", "reason": "quote not in letter"}]


def test_quote_check_drops_value_without_quote():
    facts, _, dropped = X.check_quotes(raw(physio_weeks=(5, None)), LETTER)
    assert facts["physio_weeks"] is None and dropped[0]["reason"] == "quote not in letter"


def test_quote_check_ignores_spacing_and_curly_quotes():
    assert X.quote_in_letter("Patient: Ms Aisha HALL DOB: 28/06/1954", LETTER)
    assert X.quote_in_letter("Oxford Knee Score\n today is 22", LETTER)
    assert X.quote_in_letter("it’s", "it's")
    assert not X.quote_in_letter("", LETTER)


def test_quote_check_drops_out_of_range():
    facts, _, dropped = X.check_quotes(raw(oks=(22, "Oxford Knee Score today is 22"), kl=(9, "KL3")), LETTER)
    assert facts["oks"] == 22 and facts["kl"] is None
    assert dropped[0]["reason"] == "out of range"


def test_diabetes_false_needs_no_quote_but_true_does():
    assert X.check_quotes(raw(diabetes=(False, None)), LETTER)[0]["diabetes"] is False
    assert X.check_quotes(raw(diabetes=(True, "Type 2 diabetes")), LETTER)[0]["diabetes"] is None


# ---------------------------------------------------------------- cache

def test_cache_path_has_model_and_letter_id(tmp_cache):
    assert X.cache_path("L0001") == tmp_cache / "claude-test" / "L0001.json"


def test_first_call_writes_cache_second_uses_it(tmp_cache, fake_llm):
    first = X.extract(LETTER, "L0001")
    second = X.extract(LETTER, "L0001")
    assert len(fake_llm) == 1
    assert not first.from_cache and second.from_cache
    assert first.facts == second.facts and first.model == "claude-test"
    saved = json.loads((tmp_cache / "claude-test" / "L0001.json").read_text())
    assert saved["model"] == "claude-test" and saved["letter_id"] == "L0001"
    assert saved["raw"]["oks"] == {"value": 22, "quote": "Oxford Knee Score today is 22"}


def test_changed_letter_or_refresh_calls_again(tmp_cache, fake_llm):
    X.extract(LETTER, "L0001")
    X.extract(LETTER + "Addendum.\n", "L0001")
    X.extract(LETTER + "Addendum.\n", "L0001", refresh=True)
    assert len(fake_llm) == 3


def test_other_model_has_its_own_cache(tmp_cache, fake_llm, monkeypatch):
    X.extract(LETTER, "L0001")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-other")
    assert not X.extract(LETTER, "L0001").from_cache
    assert (tmp_cache / "claude-other" / "L0001.json").exists()


def test_demo_mode_never_calls_api(tmp_cache, fake_llm, monkeypatch):
    X.extract(LETTER, "L0001")
    monkeypatch.setenv("DEMO_MODE", "1")
    assert X.extract(LETTER, "L0001").from_cache
    with pytest.raises(X.DemoCacheMiss):
        X.extract(LETTER, "L0002")
    assert len(fake_llm) == 1


# ---------------------------------------------------------------- rules

def test_decide_letter_uses_rules_and_waiting_list_weeks():
    facts = X.check_quotes(GOOD, LETTER)[0]
    d = X.decide_letter(facts, weeks_waiting=30)
    assert d["pathway"] == "physio" and d["label"] == "Physio first" and d["rule"] == 3
    assert d["priority"] > X.decide_letter(facts, weeks_waiting=0)["priority"]


def test_missing_score_means_ask_gp():
    facts = X.check_quotes(raw(kl=(3, "KL3"), physio_weeks=(5, "five weeks of physiotherapy")), LETTER)[0]
    d = X.decide_letter(facts)
    assert d["pathway"] == "review" and "No Oxford Knee Score" in d["reasons"]


# ---------------------------------------------------------------- letter files

def test_read_letter_txt_and_docx():
    assert X.read_letter("a.txt", LETTER.encode()) == LETTER
    doc = Document()
    doc.add_paragraph("Oxford Knee Score 18")
    buf = io.BytesIO()
    doc.save(buf)
    assert "Oxford Knee Score 18" in X.read_letter("a.DOCX", buf.getvalue())
    with pytest.raises(ValueError):
        X.read_letter("a.rtf", b"")


def test_age_worked_out_from_quoted_dates():
    r = raw(date_of_birth=("28/06/1954", "DOB: 28/06/1954"), letter_date=("25/04/2026", "25/04/2026"))
    facts, quotes, _ = X.check_quotes(r, LETTER + "Referral date: 25/04/2026\n")
    assert facts["age"] == 71 and quotes["age"] == "DOB: 28/06/1954"


def test_age_not_worked_out_from_unquoted_date():
    r = raw(date_of_birth=("28/06/1954", "DOB: 28/06/1954"), letter_date=("25/04/2026", "Letter date 25/04/2026"))
    assert X.check_quotes(r, LETTER)[0]["age"] is None


def test_age_on():
    assert X.age_on("28/06/1954", "27/06/2026") == 71
    assert X.age_on("28/06/1954", "28/06/2026") == 72
    assert X.age_on("31/02/1954", "28/06/2026") is None
    assert X.age_on(None, "28/06/2026") is None


def test_prompt_change_invalidates_cache(tmp_cache, fake_llm, monkeypatch):
    X.extract(LETTER, "L0001")
    monkeypatch.setattr(X, "SYSTEM", X.SYSTEM + " Extra rule.")
    assert not X.extract(LETTER, "L0001").from_cache


def test_xray_finding_value_is_the_checked_quote():
    r = raw(xray_finding=("Moderate osteophytes, narrowing", "Moderate osteophytes with definite joint space narrowing"))
    facts, _, dropped = X.check_quotes(r, LETTER)
    assert facts["xray_finding"] == "Moderate osteophytes with definite joint space narrowing" and dropped == []


@pytest.mark.parametrize("value", ["Mrs Aisha HALL", "Ms. Aisha HALL", "Aisha HALL"])
def test_name_drops_title(value):
    assert X.check_quotes(raw(name=(value, "Ms Aisha HALL")), LETTER)[0]["name"] == "Aisha HALL"


def test_name_keeps_names_that_start_like_titles():
    assert X.TITLE.sub("", "Mrsha Doran") == "Mrsha Doran"
