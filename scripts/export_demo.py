"""Export the demo data the frontend reads until the backend exists. Never calls the API.

For every letter with a cached extraction (dev and test sets): run the quote check, match the NHS number to the
cleaned waiting list, apply rules.py (pathway, rule, priority and its breakdown), and find where each quote sits
in the letter so the app can highlight it.

    python scripts/export_demo.py
      -> frontend/public/demo/queue.json, patients/<id>.json, week.json, waiting_list.json, results.json
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


def write_import_demo() -> None:
    """Spreadsheet import on the static demo: the template, the sample file, and the sample's preview and import
    result, computed by the real backend code against a throwaway database (so the demo can't drift from it)."""
    import tempfile
    from kneedss import importer as I
    (DEMO.parent / "import_template.csv").write_text(I.template_csv())
    sample = ROOT / "data" / "samples" / "import_sample.csv"
    (DEMO.parent / "samples").mkdir(exist_ok=True)
    write(DEMO.parent / "samples" / "import_sample.csv", sample.read_text())
    data = sample.read_bytes()
    preview = I.preview(sample.name, data)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/demo.db"
        from sqlmodel import Session
        from backend import services as BS
        from backend.db import Patient, get_engine, init_db
        init_db()
        with Session(get_engine()) as session:
            commit = BS.import_commit(session, sample.name, data, {c["header"]: c["field"] for c in preview["columns"]},
                                      "demo")
            patients = {r["id"]: BS.patient_out(session, session.get(Patient, r["id"])) for r in commit["referrals"]}
        get_engine().dispose()
        del os.environ["DATABASE_URL"]
    commit.pop("import_id", None)
    write(DEMO / "import_sample.json", json.dumps({"preview": preview, "commit": commit, "patients": patients},
                                                   default=jsonable))


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
                "letter_text": text,                    # the reading model stays in the cache, not public
            }
            write(DEMO / "patients" / f"{pid}.json", json.dumps(patient, default=jsonable))
            written.add(f"{pid}.json")
            queue.append({k: patient[k] for k in ("id", "letter_id", "set", "name", "nhs_number", "pathway", "rule",
                                                   "priority", "weeks_waiting", "weight_support")}
                         | {"filename": f"{lid}.txt", "text_key": text_key(text)})
    for old in (DEMO / "patients").glob("*.json"):
        if old.name not in written:               # patients no longer in the queue (and stray sync copies)
            old.unlink()
    queue.sort(key=lambda r: (-r["priority"], -(r["weeks_waiting"] or 0)))
    write(DEMO / "queue.json", json.dumps(queue))
    # the week as the backend plans it: the waiting list, with the newest letter's pathway and priority
    week = wl[["patient_id", "pathway", "priority_score", "weeks_waiting"]].copy()
    from_letter = {r["id"]: r for r in queue if r["weeks_waiting"] is not None}
    week["pathway"] = [from_letter[i]["pathway"] if i in from_letter else p for i, p in zip(week.patient_id, week.pathway)]
    week["priority_score"] = [from_letter[i]["priority"] if i in from_letter else int(v) for i, v in zip(week.patient_id, week.priority_score)]
    names = dict(zip(wl.patient_id, wl.first_name + " " + wl.surname))
    pages = {r["id"] for r in queue}
    plan = O.plan_to_json(O.optimise(week), week, names, pages, WEEK_OF)
    write(DEMO / "week.json", json.dumps(plan, default=jsonable))
    # everyone, compact, so the demo site can re-plan the week in the browser with this browser's overrides and bookings
    write(DEMO / "waiting_list.json", json.dumps({
        "week_of": WEEK_OF, "capacity": O.CAPACITY, "long_wait": O.LONG_WAIT,
        "columns": ["id", "name", "pathway", "priority", "weeks_waiting", "has_page"],
        "rows": [[r.patient_id, names[r.patient_id], r.pathway, int(r.priority_score), int(r.weeks_waiting), r.patient_id in pages]
                 for r in week.itertuples()]}, separators=(",", ":")))

    write_import_demo()
    results = build_results()
    write(DEMO / "results.json", json.dumps(results, default=jsonable))

    size = sum(f.stat().st_size for f in DEMO.rglob("*.json"))
    counts = pd.Series([r["pathway"] for r in queue]).value_counts().to_dict()
    print(f"{len(queue)} referrals -> {DEMO.relative_to(ROOT)}/ ({size / 1e6:.1f} MB); pathways {counts}")
    print(f"on waiting list: {sum(r['weeks_waiting'] is not None for r in queue)}; "
          f"highlights: {sum(len(json.loads((DEMO / 'patients' / (r['id'] + '.json')).read_text())['spans']) for r in queue)}")


if __name__ == "__main__":
    main()
