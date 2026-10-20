import importlib.util
from pathlib import Path

from kneedss.rules import PRIORITY_MAX, priority_breakdown, priority_score

spec = importlib.util.spec_from_file_location("export_demo", Path(__file__).parent.parent / "scripts" / "export_demo.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def test_quote_spans_ignore_line_breaks():
    text = "Her Oxford knee score recorded\nat 15. Sleeps well."
    spans = E.quote_spans(text, {"oks": "Oxford knee score recorded at 15", "night_pain": "Sleeps well"})
    assert [(s["field"], text[s["start"]:s["end"]]) for s in spans] == [
        ("oks", "Oxford knee score recorded\nat 15"), ("night_pain", "Sleeps well")]


def test_text_key_ignores_spacing():
    assert E.text_key("a  b\nc ") == E.text_key("a b c")
    assert E.text_key("a b c") != E.text_key("a b d")


def test_priority_breakdown_adds_up_to_the_score():
    f = {"oks": 21, "oks_before": 25, "kl": 4, "weeks_waiting": 40, "night_pain": True, "lives_alone_or_carer": False}
    parts = priority_breakdown(f)
    assert parts == {"pain_function": 27, "xray": 20, "decline": 8, "waiting": 8, "social": 4}
    assert all(parts[k] <= PRIORITY_MAX[k] for k in parts)
    assert priority_score(f) == round(sum(parts.values()) / 108 * 100)
