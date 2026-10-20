"""Export the demo data the frontend reads until the backend exists. Never calls the API.

For every letter with a cached extraction (dev and test sets): run the quote check, match the NHS number to the
cleaned waiting list, apply rules.py (pathway, rule, priority and its breakdown), and find where each quote sits
in the letter so the app can highlight it.

    python scripts/export_demo.py
      -> frontend/public/demo/queue.json, patients/<id>.json, week.json, results.json
"""
from __future__ import annotations

import hashlib
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
from kneedss import optimise as O                  # noqa: E402
from kneedss.rules import PRIORITY_MAX             # noqa: E402

OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results"
DEMO = ROOT / "frontend" / "public" / "demo"
LETTER_SETS = [("dev", OUT / "letters.jsonl"), ("test", OUT / "test" / "letters.jsonl")]

WEEK_OF = "2026-10-26"


def text_key(text: str) -> str:
    """Fingerprint used to recognise an uploaded copy of a demo letter (spacing ignored)."""
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()


def quote_spans(text: str, quotes: dict[str, str]) -> list[dict]:
    """Where each quote sits in the letter. The quote check ignores spacing, so the search does too."""
    spans = []
    for field, q in quotes.items():
        m = re.search(r"\s+".join(map(re.escape, q.split())), text)
        if m:
            spans.append({"field": field, "start": m.start(), "end": m.end()})
    return sorted(spans, key=lambda s: (s["start"], -s["end"]))


def jsonable(v):
    if hasattr(v, "item"):
        return v.item()
    return None if isinstance(v, float) and v != v else v


def week_plan(wl: pd.DataFrame, with_page: set[str]) -> dict:
    """The optimiser's plan for this week on the cleaned waiting list (stage 5)."""
    plan = O.optimise(wl)
    names = wl.set_index("patient_id").apply(lambda r: f"{r.first_name} {r.surname}", axis=1)
    eligible = wl[wl.pathway.isin(O.ALLOWED)]

    def person(r) -> dict:
        return {"id": r.patient_id, "name": names[r.patient_id], "pathway": r.pathway, "priority": int(r.priority_score),
                "weeks_waiting": int(r.weeks_waiting), "long_wait": bool(r.long_wait), "reason": r.reason,
                "has_page": r.patient_id in with_page}

    lists = []
    for slot, label in O.SLOT_NAMES.items():
        chosen = plan.assigned[plan.assigned.slot == slot]
        can_use = eligible.pathway.map(lambda p: slot in O.ALLOWED[p])
        lists.append({"kind": slot, "label": label, "capacity": plan.capacity[slot],
                      "in": [person(r) for r in chosen.itertuples()],
                      "next": [person(r) for r in plan.next[slot].itertuples()],
                      "waiting": int(can_use.sum()) - len(chosen)})
    return {"week_of": WEEK_OF, "method": "optimiser", "status": plan.status, "shortfall": plan.shortfall,
            "patients": len(eligible), "lists": lists,
            "long_wait": {k: (len(v) if k == "unmet" else v) for k, v in plan.long_wait.items()}}


def optimise_results() -> dict | None:
    """Stage 5 simulation summary for the Results page (eval/eval_optimise.py must have been run)."""
    path = RESULTS / "optimise" / "optimise_summary.json"
    if not path.exists():
        return None
    o = json.loads(path.read_text())
    keep = ("policy", "surgery_capacity", "over_18_end", "over_52_end", "over_52_mean", "over_52_skipped_patients",
            "weeks_infeasible", "mean_wait_surgery", "mean_oks_operated")
    return {"weeks": o["weeks"], "arrival_rate": round(o["arrival_rate"], 1), "capacity": o["capacity"],
            "thresholds": o["thresholds"], "seeds": o["seeds"], "metrics": o["metrics"],
            "triage_off_scenario": o["triage_off_scenario"], "triage_off_rule": o["triage_off_rule"], "series": o["series"],
            "summary": [{k: r[k] for k in keep} for r in o["summary"]],
            "robustness": o["robustness"], "pairs": o["pairs"]}


def tree_results() -> dict | None:
    """Stage 4 summary for the Results page (eval/eval_tree.py must have been run)."""
    path = RESULTS / "tree" / "tree_summary.json"
    if not path.exists():
        return None
    t = json.loads(path.read_text())
    runs = {r["name"]: r for r in t["runs"]}
    cont, disc = runs["continuous"], runs["discretised"]
    banded_cut = {x["rule"]: x for x in disc["thresholds"]}
    return {
        "truth_check": {k: t["truth_check"][k] for k in ("patients", "matching")},
        "train": t["train"], "test": t["test"],
        "runs": [{k: r[k] for k in ("name", "agreement", "agreement_complete", "cv_accuracy", "depth", "leaves",
                                    "best_params", "test_patients")} | {"disagreements": len(r["disagreements"])}
                 for r in (cont, disc)],
        "thresholds": [{"rule": x["rule"], "short": x["short"], "rule_cut": x["rule_cut"], "tree": x["tree_nearest"],
                        "same": x["same_cut"], "banded": banded_cut[x["rule"]]["tree_nearest"],
                        "banded_same": banded_cut[x["rule"]]["same_cut"]}
                       for x in cont["thresholds"]],
        # the cut points the banded tree can't draw, and the band edge it used instead
        "band_misses": [{"short": x["short"], "rule_cut": x["rule_cut"], "band_edge": x["tree_nearest"]}
                        for x in disc["thresholds"] if not x["same_cut"] and x["tree_nearest"] is not None],
        "disagreements": [{k: d[k] for k in ("patient_id", "oks", "kl_grade", "bmi", "physio_weeks", "oks_drop",
                                              "rules", "tree", "model")} for d in cont["disagreements"] + disc["disagreements"]],
        "importances": cont["importances"],
        "tree_text": (RESULTS / "tree" / "tree_rules.txt").read_text(),
    }


def main() -> None:
    wl = pd.read_csv(OUT / "waiting_list.csv", dtype={"nhs_number": str})
    wl["nhs"] = wl.nhs_number.str.replace(r"\D", "", regex=True)
    by_nhs = wl.set_index("nhs")

    (DEMO / "patients").mkdir(parents=True, exist_ok=True)
    for old in (DEMO / "patients").glob("*.json"):
        old.unlink()
    queue = []
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
            (DEMO / "patients" / f"{pid}.json").write_text(json.dumps(patient, default=jsonable))
            queue.append({k: patient[k] for k in ("id", "letter_id", "set", "name", "pathway", "rule", "priority",
                                                   "weeks_waiting", "weight_support")}
                         | {"text_key": text_key(text)})
    queue.sort(key=lambda r: (-r["priority"], -(r["weeks_waiting"] or 0)))
    (DEMO / "queue.json").write_text(json.dumps(queue))
    (DEMO / "week.json").write_text(json.dumps(week_plan(wl, {r["id"] for r in queue}), default=jsonable))

    # results: extraction (dev and held-out test) and cleaning
    by_issue = pd.read_csv(RESULTS / "cleaning_by_issue.csv")
    actions = pd.read_csv(OUT / "cleaning_actions.csv")
    raw_rows = sum(1 for _ in open(OUT / "patients_raw.csv")) - 1
    extraction = {}
    for name, p in [("dev", RESULTS / "extraction_summary.json"), ("test", RESULTS / "test" / "extraction_summary.json")]:
        s = json.loads(p.read_text())
        extraction[name] = {k: s[k] for k in ("letters", "model", "mean_field_accuracy", "letters_all_fields_right",
                                              "quote_hit_rate", "facts_dropped", "pathway_agreement",
                                              "priority_mae", "field_accuracy")} \
            | {"cost_usd": (s.get("usage") or {}).get("cost_usd")}
    results = {
        "extraction": extraction,
        "cleaning": {
            "raw_rows": raw_rows, "patients": len(wl),
            "duplicates_removed": int((actions.field == "(row)").sum()),
            "logged": int(by_issue.logged.sum()), "fixed": int(by_issue.fixed.sum()),
            "set_missing": int(by_issue["set missing"].sum()), "wrong": int(by_issue.wrong.sum()),
            "by_issue": by_issue.to_dict(orient="records"),
        },
        "decision_tree": tree_results(),
        "optimise": optimise_results(),
    }
    (DEMO / "results.json").write_text(json.dumps(results, default=jsonable))

    size = sum(f.stat().st_size for f in DEMO.rglob("*.json"))
    counts = pd.Series([r["pathway"] for r in queue]).value_counts().to_dict()
    print(f"{len(queue)} referrals -> {DEMO.relative_to(ROOT)}/ ({size / 1e6:.1f} MB); pathways {counts}")
    print(f"on waiting list: {sum(r['weeks_waiting'] is not None for r in queue)}; "
          f"highlights: {sum(len(json.loads((DEMO / 'patients' / (r['id'] + '.json')).read_text())['spans']) for r in queue)}")


if __name__ == "__main__":
    main()
