"""Check the cleaned waiting list against the data-quality log and the ground truth.

For every logged problem: was it fixed (clean value = true value), set to missing (can't be recovered), or left
wrong? Then every cell of the cleaned table is compared with patients_clean.csv (the generator's truth), so
changes the log doesn't explain also show up. Writes eval/results/cleaning_summary.md and CSV tables.

    python eval/eval_cleaning.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import clean as C            # noqa: E402
from kneedss.rules import PATHWAYS        # noqa: E402

OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results"
COMPARE = ["nhs_number", "title", "first_name", "surname", "sex_code", "sex", "date_of_birth", "age", "laterality",
           "referral_date", "weeks_waiting", "kl_grade", "oks", "oks_before", "physio_weeks", "injections", "bmi",
           "smoking_status", "diabetes", "night_pain", "lives_alone", "carer"]


def same(a, b) -> bool:
    if pd.isna(a) or pd.isna(b):
        return pd.isna(a) and pd.isna(b)
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a) == str(b)


def main() -> None:
    raw = pd.read_csv(OUT / "patients_raw.csv", dtype=str, keep_default_na=False)
    log = pd.read_csv(OUT / "data_quality_log.csv")
    truth = pd.read_csv(OUT / "patients_clean.csv").set_index("patient_id")
    df, actions = C.clean(raw)
    clean = df.set_index("patient_id")

    # 1. every logged problem
    cell_log = log[log.field != "(row)"].copy()
    cell_log["clean_value"] = [clean.at[p, f] for p, f in zip(cell_log.patient_id, cell_log.field)]
    cell_log["outcome"] = ["fixed" if same(c, t) else "set missing" if pd.isna(c) else "wrong"
                           for c, t in zip(cell_log.clean_value, cell_log.true_value)]
    by_issue = (cell_log.groupby(["field", "issue", "outcome"]).size().unstack(fill_value=0)
                .reindex(columns=["fixed", "set missing", "wrong"], fill_value=0))
    by_issue["logged"] = by_issue.sum(axis=1)
    by_issue = by_issue[["logged", "fixed", "set missing", "wrong"]].reset_index()
    dup_logged = set(log[log.field == "(row)"].patient_id)
    dup_removed = set(actions[actions.field == "(row)"].patient_id)

    # 2. every cell against the truth
    cells = []
    for col in COMPARE:
        t, c = truth[col].reindex(clean.index), clean[col]
        match = [same(a, b) for a, b in zip(c, t)]
        missing = c.isna() & t.notna()
        wrong = [not m and not ms for m, ms in zip(match, missing)]
        cells.append({"field": col, "cells": len(c), "match truth": sum(match), "missing": int(missing.sum()),
                      "wrong": sum(wrong), "wrong patients": ", ".join(c.index[wrong][:5])})
    cells = pd.DataFrame(cells)
    logged_cells = set(zip(cell_log.patient_id, cell_log.field))
    changed = set(zip(actions.patient_id, actions.field)) - {(p, "(row)") for p in dup_removed}
    unlogged = sorted(changed - logged_cells)

    # 3. pathway from the cleaned facts vs from the full (true) record
    path = pd.crosstab(truth.true_pathway.reindex(clean.index).map(PATHWAYS), clean.pathway.map(PATHWAYS),
                       rownames=["full record"], colnames=["cleaned data"])
    agree = (clean.pathway == truth.true_pathway.reindex(clean.index)).mean()

    RESULTS.mkdir(parents=True, exist_ok=True)
    by_issue.to_csv(RESULTS / "cleaning_by_issue.csv", index=False)
    cells.to_csv(RESULTS / "cleaning_cells.csv", index=False)
    totals = by_issue[["logged", "fixed", "set missing", "wrong"]].sum()
    missing_after = df[["oks", "kl_grade", "bmi", "physio_weeks", "smoking_status"]].isna().sum()
    bands = {name: df[col].fillna("missing").value_counts().rename_axis(name)
             .to_frame("patients") for name, col in [("OKS band", "oks_band"), ("BMI category", "bmi_category"),
                                                     ("Wait band", "wait_band")]}
    lines = [
        "# Cleaning summary", "",
        f"Raw rows: {len(raw):,}. Patients after cleaning: {len(df):,}. Changes made: {len(actions):,}.", "",
        "| Check | Result |", "|---|---|",
        f"| Duplicate referrals removed | {len(dup_removed)} of {len(dup_logged)} logged"
        f" ({'same patients' if dup_removed == dup_logged else 'DIFFERENT patients'}) |",
        f"| Logged cell problems | {int(totals.logged)} |",
        f"| Fixed (clean value = true value) | {int(totals.fixed)} ({totals.fixed / totals.logged:.1%}) |",
        f"| Set missing (true value can't be recovered) | {int(totals['set missing'])} ({totals['set missing'] / totals.logged:.1%}) |",
        f"| Left wrong | {int(totals.wrong)} |",
        f"| Changes the log doesn't explain | {len(unlogged)}" + (f": {', '.join(f'{p} {f}' for p, f in unlogged)}" if unlogged else "") + " |",
        f"| Pathway from cleaned data = pathway from full record | {agree:.1%} |",
        "", "## Logged problems by issue", "", by_issue.to_markdown(index=False), "",
        "## Every cell against the truth", "",
        "Missing = the truth has a value the cleaned table doesn't (it was lost in the raw file).", "",
        cells.to_markdown(index=False), "",
        "## Missing after cleaning", "", missing_after.to_frame("patients").to_markdown(), "",
        "## Pathway: full record vs cleaned data", "",
        "Patients with a missing score, X-ray grade or physiotherapy history go to \"Ask the GP\".", "",
        path.to_markdown(), "",
        "## Bands", "",
        *[part for b in bands.values() for part in (b.to_markdown(), "")],
    ]
    md = "\n".join(lines)
    (RESULTS / "cleaning_summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
