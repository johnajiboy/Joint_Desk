"""The evaluation results the Results page shows, read from eval/results/ (and the cleaning outputs).

Used by scripts/export_demo.py (demo JSON) and by the backend's GET /results, so both serve the same numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results"


def extraction_results() -> dict:
    out = {}
    for name, p in [("dev", RESULTS / "extraction_summary.json"), ("test", RESULTS / "test" / "extraction_summary.json")]:
        s = json.loads(p.read_text())
        # no model or provider name in anything served to users (it stays in eval/results for the report)
        out[name] = {k: s[k] for k in ("letters", "mean_field_accuracy", "letters_all_fields_right",
                                       "quote_hit_rate", "facts_dropped", "pathway_agreement",
                                       "priority_mae", "field_accuracy")} \
            | {"cost_usd": (s.get("usage") or {}).get("cost_usd")}
    return out


def cleaning_results() -> dict:
    by_issue = pd.read_csv(RESULTS / "cleaning_by_issue.csv")
    actions = pd.read_csv(OUT / "cleaning_actions.csv")
    return {
        "raw_rows": sum(1 for _ in open(OUT / "patients_raw.csv")) - 1,
        "patients": sum(1 for _ in open(OUT / "waiting_list.csv")) - 1,
        "duplicates_removed": int((actions.field == "(row)").sum()),
        "logged": int(by_issue.logged.sum()), "fixed": int(by_issue.fixed.sum()),
        "set_missing": int(by_issue["set missing"].sum()), "wrong": int(by_issue.wrong.sum()),
        "by_issue": by_issue.to_dict(orient="records"),
    }


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
            "robustness": o["robustness"], "pairs": o["pairs"], "surgery_list": o.get("surgery_list")}


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
                                              "rules", "tree")}
                          | {"features": "raw values" if d["model"] == "continuous" else "NHS bands"}
                          for d in cont["disagreements"] + disc["disagreements"]],
        "importances": cont["importances"],
        "tree_text": (RESULTS / "tree" / "tree_rules.txt").read_text(),
    }


def backlog_results() -> dict:
    """The current waiting list (cleaned): how many need a slot, how long they have waited, where referrals went."""
    from kneedss.optimise import ALLOWED, LONG_WAIT, STANDARD_WEEKS
    wl = pd.read_csv(OUT / "waiting_list.csv")
    slot = wl[wl.pathway.isin(list(ALLOWED))]
    return {
        "patients": len(wl), "waiting_for_slot": len(slot), "surgery": int((wl.pathway == "surgery").sum()),
        "over_standard": int((slot.weeks_waiting > STANDARD_WEEKS).sum()), "over_long_wait": int((slot.weeks_waiting > LONG_WAIT).sum()),
        "standard_weeks": STANDARD_WEEKS, "long_wait_weeks": LONG_WAIT,
        "by_pathway": {k: int(v) for k, v in wl.pathway.value_counts().items()},
    }


def build_results() -> dict:
    return {"extraction": extraction_results(), "cleaning": cleaning_results(),
            "decision_tree": tree_results(), "optimise": optimise_results(), "backlog": backlog_results()}
