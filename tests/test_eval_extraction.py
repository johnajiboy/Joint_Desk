import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("eval_extraction", Path(__file__).parent.parent / "eval" / "eval_extraction.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def test_same():
    assert E.same("oks", None, None)
    assert not E.same("oks", 22, None)
    assert E.same("oks", 22, 22)
    assert E.same("name", "Aisha Hall", "Aisha HALL")
    assert E.same("bmi", 25.4, 25.40001)
    assert not E.same("bmi", 25.4, 25.5)
    assert E.same("xray_finding", "Moderate osteophytes, in keeping with OA.", '"Moderate osteophytes, in keeping with OA."')


def test_outcome():
    assert E.outcome("kl", 3, 3) == "correct"
    assert E.outcome("kl", 3, 4) == "wrong"
    assert E.outcome("kl", 3, None) == "missed"
    assert E.outcome("kl", None, 3) == "extra"


def test_nhs_digits():
    assert E.nhs_digits("999 809 9129") == "9998099129"
    assert E.nhs_digits(None) == ""
