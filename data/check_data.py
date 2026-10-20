"""Check the generated data and write a summary for the report.

    python data/check_data.py                          -> checks the dev set, writes data/output/data_summary.md
    python data/check_data.py --out data/output/test   -> checks the held-out test set the same way

Fails loudly if anything is inconsistent: invalid NHS numbers, evidence that is not in its letter,
gold pathways that the rules don't reproduce, or counts that don't add up.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss.standards import is_valid_nhs_number     # noqa: E402
from kneedss.rules import decide, priority_score      # noqa: E402

OUT = ROOT / "data" / "output"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT, help="folder with the letters and answer key")
    out = ap.parse_args().out
    pts = pd.read_csv(OUT / "patients_clean.csv")
    raw = pd.read_csv(OUT / "patients_raw.csv")
    log = pd.read_csv(OUT / "data_quality_log.csv")
    keys = [json.loads(l) for l in open(out / "answer_key.jsonl")]
    letters = {json.loads(l)["letter_id"]: json.loads(l)["text"] for l in open(out / "letters.jsonl")}

    # patients
    assert pts.nhs_number.map(is_valid_nhs_number).all(), "invalid NHS number"
    assert pts.nhs_number.str.startswith("999").all(), "NHS number outside the test range"
    assert pts.nhs_number.is_unique and pts.patient_id.is_unique
    assert pts.oks.between(0, 48).all() and pts.oks_before.between(0, 48).all()
    assert pts.kl_grade.between(0, 4).all() and pts.bmi.between(15, 60).all()
    for _, p in pts.sample(200, random_state=1).iterrows():
        f = {"oks": p.oks, "oks_before": p.oks_before, "kl": p.kl_grade, "physio_weeks": p.physio_weeks, "bmi": p.bmi,
             "weeks_waiting": p.weeks_waiting, "night_pain": p.night_pain, "lives_alone_or_carer": p.lives_alone or p.carer}
        assert decide(f)["pathway"] == p.true_pathway and priority_score(f) == p.priority_score
    assert len(raw) == len(pts) + (log.issue == "duplicate referral").sum()

    # letters
    assert len(keys) == len(letters)
    for k in keys:
        t = letters[k["letter_id"]]
        assert "SYNTHETIC TEST DATA" in t
        for field, q in k["evidence"].items():
            assert q in t, f"{k['letter_id']} {field}: evidence not found"
        g = k["gold"]
        f = {"oks": g["oks"], "oks_before": g["oks_before"], "kl": g["kl"], "physio_weeks": g["physio_weeks"], "bmi": g["bmi"],
             "weeks_waiting": int(pts.set_index("patient_id").at[k["patient_id"], "weeks_waiting"]),
             "night_pain": g["night_pain"], "lives_alone_or_carer": g["lives_alone_or_carer"]}
        assert decide(f)["pathway"] == k["gold_pathway"], k["letter_id"]
        assert (out / "letters" / f"{k['letter_id']}.txt").read_text() == t, f"{k['letter_id']}: file differs"
    print("All checks passed.")

    # summary for the report
    num = pts[["age", "bmi", "oks", "oks_before", "kl_grade", "physio_weeks", "weeks_waiting", "priority_score"]]
    kdf = pd.DataFrame(keys)
    tags = pd.Series([t for k in keys for t in k["difficulty_tags"]]).value_counts()
    stated = {f: sum(k["gold"][f] is not None for k in keys) for f in keys[0]["gold"]}
    lines = [
        "# Data summary", "",
        f"Patients: {len(pts):,}. Raw rows: {len(raw):,} ({(log.issue=='duplicate referral').sum()} duplicates). "
        f"Data-quality issues logged: {len(log):,}.", "",
        "## Patients (clean)", "", num.describe().round(1).T[["mean", "std", "min", "50%", "max"]].to_markdown(), "",
        f"- Female: {(pts.sex=='Female').mean():.1%}",
        f"- Type 2 diabetes: {pts.diabetes.mean():.1%}; hypertension: {pts.hypertension.mean():.1%}; CKD: {pts.ckd.mean():.1%}",
        f"- Waiting over 18 weeks: {(pts.weeks_waiting>18).mean():.1%}; over 52 weeks: {(pts.weeks_waiting>52).mean():.1%}",
        f"- IMD deciles 1-3 (most deprived): {(pts.imd_decile<=3).mean():.1%}", "",
        "Mean Oxford Knee Score by X-ray grade: " + ", ".join(f"KL{k}: {v:.1f}" for k, v in pts.groupby('kl_grade').oks.mean().items()), "",
        "## Pathways (full record)", "", pts.true_pathway_label.value_counts().to_frame("patients").to_markdown(), "",
        "## Data-quality issues in the raw file", "", log.groupby(["field", "issue"]).size().to_frame("rows").to_markdown(), "",
        "## Letters", "",
        f"Letters: {len(keys)} ({(kdf.letter_type=='initial').sum()} initial, {(kdf.letter_type=='expedite').sum()} expedite). "
        f"Styles: " + ", ".join(f"{k} {v}" for k, v in kdf['style'].value_counts().items()) + ".", "",
        "Gold pathway from what the letter states:", "", kdf.gold_pathway_label.value_counts().to_frame("letters").to_markdown(), "",
        f"Letters whose pathway differs from the full record (because facts are missing from the letter): "
        f"{(kdf.gold_pathway!=kdf.record_pathway).sum()}", "",
        "Difficulty tags:", "", tags.to_frame("letters").to_markdown(), "",
        f"Facts stated per field (out of {len(keys)}):", "", pd.Series(stated).to_frame("letters").to_markdown(), "",
    ]
    (out / "data_summary.md").write_text("\n".join(lines))
    print("Wrote data_summary.md")


if __name__ == "__main__":
    main()
