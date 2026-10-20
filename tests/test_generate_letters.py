import importlib.util
import json
import random
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("generate_letters", ROOT / "data" / "generate_letters.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

OUT = ROOT / "data" / "output"
OLD_KL2 = ["Mild degenerative change with early medial joint space narrowing and small osteophytes.",
           "Early osteoarthritic change, predominantly medial compartment."]


@pytest.fixture(scope="module")
def pts():
    return pd.read_csv(OUT / "patients_clean.csv")


def test_rewrite_keeps_quotes_exact():
    text = "She has osteoarthritis of the right knee and lives with family."
    ev = {"side": "right knee", "social": "lives with family"}
    edits = [(text.index("osteoarthritis"), text.index("osteoarthritis") + 14, "OA", True),
             (text.index("right knee"), text.index("right knee") + 10, "R) knee", True),
             (text.index("with"), text.index("with") + 4, "w/", True)]
    new, ev2 = G.rewrite(text, ev, edits)
    assert new == "She has OA of the R) knee and lives w/ family."
    assert ev2 == {"side": "R) knee", "social": "lives w/ family"}


def test_rewrite_skips_edits_across_quote_edges_and_protected_quotes():
    text = "X-ray: Moderate osteophytes and sclerosis. Walks with a stick."
    ev = {"xray_finding": "Moderate osteophytes and sclerosis.", "walking_aid": "with a stick"}
    a = text.index(" and ")
    edits = [(a + 1, a + 4, "&", True),                                  # inside a protected quote
             (text.index("Walks with"), text.index("Walks with") + 10, "Walks w/", True)]  # crosses an edge
    new, ev2 = G.rewrite(text, ev, edits)
    assert new == text and ev2 == ev


def test_hard_letters_keep_every_quote_and_gold(pts):
    letters = G.generate(pts, 40, 99, prefix="T", hard=True)
    tags = set()
    for text, key in letters:
        assert key["letter_id"].startswith("T")
        for field, q in key["evidence"].items():
            assert q in text, (key["letter_id"], field)
        tags |= set(key["difficulty_tags"])
    assert {"shorthand", "typos", "reordered", "scanned"} <= tags


def test_exclude_keeps_patients_out(pts):
    first = {k["patient_id"] for _, k in G.generate(pts, 30, 5)}
    second = {k["patient_id"] for _, k in G.generate(pts, 30, 5, exclude=first)}
    assert not first & second


def test_dev_set_still_reproduces_except_kl2_wording(pts):
    """Same seed, same letters: only letters that used the old KL 2 wording differ, and only in that line."""
    saved = [json.loads(line) for line in open(OUT / "letters.jsonl")]
    for (text, key), old in zip(G.generate(pts, 150, 11), saved):
        assert key["letter_id"] == old["letter_id"]
        if text != old["text"]:
            changed = [(a, b) for a, b in zip(old["text"].splitlines(), text.splitlines()) if a != b]
            assert len(changed) == 1 and any(w.rstrip(".") in changed[0][0] for w in OLD_KL2), key["letter_id"]


def test_kl2_wording_has_no_early():
    from kneedss.standards import KL_REPORT_WORDING
    assert not any("early" in w.lower() for w in KL_REPORT_WORDING[2])
    assert len(KL_REPORT_WORDING[2]) == 3      # same count keeps the random draws aligned
