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


def test_usage_totals_skip_letters_without_usage():
    rs = [{"usage": {"input_tokens": 100, "output_tokens": 10, "cache_read_input_tokens": 0,
                     "cache_creation_input_tokens": 0, "attempts": 1, "cost_usd": 0.5}, "from_cache": False},
          {"usage": None, "from_cache": True}]
    u = E.usage_totals(rs)
    assert u["letters_recorded"] == 1 and u["read_this_run"] == 1
    assert u["input_tokens"] == 100 and u["cost_usd"] == 0.5
