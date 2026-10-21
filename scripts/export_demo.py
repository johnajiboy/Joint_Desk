"""Export the demo data the frontend reads until the backend exists. Never calls the API.

For every letter with a cached extraction (dev and test sets): run the quote check, match the NHS number to the
cleaned waiting list, apply rules.py (pathway, rule, priority and its breakdown), and find where each quote sits
in the letter so the app can highlight it.

    python scripts/export_demo.py
      -> frontend/public/demo/queue.json, patients/<id>.json, week.json, results.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DEMO_MODE"] = "1"                      # cache only: this script must never call the API
from kneedss import extract as X                   # noqa: E402
from kneedss.extract import quote_spans, text_key  # noqa: E402,F401  (re-exported for tests)
from kneedss import optimise as O                  # noqa: E402
from kneedss.results import build_results         # noqa: E402
from kneedss.rules import PRIORITY_MAX             # noqa: E402

OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results"
DEMO = ROOT / "frontend" / "public" / "demo"
LETTER_SETS = [("dev", OUT / "letters.jsonl"), ("test", OUT / "test" / "letters.jsonl")]

WEEK_OF = "2026-10-26"


def write(path: Path, text: str) -> None:
    """Write only when the content changed. Deleting and rewriting unchanged files makes iCloud Drive (this repo
    lives on a synced Desktop) leave "name 2.json" copies behind."""
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def jsonable(v):
    if hasattr(v, "item"):
        return v.item()
    return None if isinstance(v, float) and v != v else v


def main() -> None:
    wl = pd.read_csv(OUT / "waiting_list.csv", dtype={"nhs_number": str})
    wl["nhs"] = wl.nhs_number.str.replace(r"\D", "", regex=True)
    by_nhs = wl.set_index("nhs")

    (DEMO / "patients").mkdir(parents=True, exist_ok=True)
    queue, written = [], set()
    for set_name, path in LETTER_SETS:
        for d in map(json.loads, open(path)):
            lid, text = d["letter_id"], d["text"]
            ex = X.extract(text, lid)                       # raises DemoCacheMiss rather than calling the API
            nhs = re.sub(r"\D", "", str(ex.facts["nhs_number"] or ""))
            rec = by_nhs.loc[nhs] if nhs in by_nhs.index else None
            weeks = int(rec.weeks_waiting) if rec is not None else None
            dec = X.decide_letter(ex.facts, weeks)
            pid = rec.patient_id if rec is not None else lid
            name = f"{rec.first_name} {rec.surname}" if rec is not None else ex.facts["name"]
            patient = {
                "id": pid, "letter_id": lid, "set": set_name, "name": name,
                "nhs_number": rec.nhs_number if rec is not None else ex.facts["nhs_number"],
                "on_waiting_list": rec is not None, "weeks_waiting": dec["facts_used"]["weeks_waiting"],
                "facts": {k: jsonable(v) for k, v in ex.facts.items()}, "quotes": ex.quotes,
                "spans": quote_spans(text, ex.quotes), "dropped": ex.dropped,
                "pathway": dec["pathway"], "label": dec["label"], "rule": dec["rule"], "reasons": dec["reasons"],
                "weight_support": dec["weight_support"], "priority": dec["priority"],
                "priority_parts": dec["priority_parts"], "priority_max": PRIORITY_MAX,
                "model": ex.model, "letter_text": text,
            }
            write(DEMO / "patients" / f"{pid}.json", json.dumps(patient, default=jsonable))
            written.add(f"{pid}.json")
            queue.append({k: patient[k] for k in ("id", "letter_id", "set", "name", "pathway", "rule", "priority",
                                                   "weeks_waiting", "weight_support")}
                         | {"text_key": text_key(text)})
    for old in (DEMO / "patients").glob("*.json"):
        if old.name not in written:               # patients no longer in the queue (and stray sync copies)
            old.unlink()
    queue.sort(key=lambda r: (-r["priority"], -(r["weeks_waiting"] or 0)))
    write(DEMO / "queue.json", json.dumps(queue))
    names = dict(zip(wl.patient_id, wl.first_name + " " + wl.surname))
    plan = O.plan_to_json(O.optimise(wl), wl, names, {r["id"] for r in queue}, WEEK_OF)
    write(DEMO / "week.json", json.dumps(plan, default=jsonable))

    results = build_results()
    write(DEMO / "results.json", json.dumps(results, default=jsonable))

    size = sum(f.stat().st_size for f in DEMO.rglob("*.json"))
    counts = pd.Series([r["pathway"] for r in queue]).value_counts().to_dict()
    print(f"{len(queue)} referrals -> {DEMO.relative_to(ROOT)}/ ({size / 1e6:.1f} MB); pathways {counts}")
    print(f"on waiting list: {sum(r['weeks_waiting'] is not None for r in queue)}; "
          f"highlights: {sum(len(json.loads((DEMO / 'patients' / (r['id'] + '.json')).read_text())['spans']) for r in queue)}")


if __name__ == "__main__":
    main()
