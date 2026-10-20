"""Generate a synthetic knee osteoarthritis referral waiting list (default 1,500 patients).

    python data/generate_patients.py              # writes data/output/
    python data/generate_patients.py --n 2000 --seed 7

Outputs
  patients_clean.csv      the true values (ground truth for every check)
  patients_raw.csv        the same patients with realistic data-quality problems added, for the cleaning step
  data_quality_log.csv    every problem added to the raw file: row, field, true value, raw value, issue type

Every distribution is listed with its source or stated as an assumption in docs/assumptions.md.
Fields that appear together are correlated (e.g. worse X-ray grade -> lower Oxford Knee Score), so the
data can support knowledge extraction rather than being independent noise.
"""
from __future__ import annotations
import argparse, random, sys
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import standards as S          # noqa: E402
from kneedss.rules import decide, priority_score, PATHWAYS   # noqa: E402

EXTRACT_DATE = date(2026, 10, 20)           # the day the waiting list snapshot is taken
OUT = ROOT / "data" / "output"


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def age_on(dob: date, on: date = EXTRACT_DATE) -> int:
    """Age in whole years on a date."""
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def make_patient(i: int, rng: random.Random, nrng: np.random.Generator, used_nhs: set) -> dict:
    # --- demographics (NJR: ~57% of primary knee replacements are in women; median age ~70)
    sex = "2" if rng.random() < 0.57 else "1"
    # The drawn age sets the date of birth and the age-related risks below; the stored age is always worked out
    # from the date of birth on the extract date, so the two can never disagree.
    age = int(round(clip(nrng.normal(69, 9.5), 45, 92)))
    dob = EXTRACT_DATE - timedelta(days=int(age * 365.25 + rng.randint(0, 364)))
    first = rng.choice(S.FIRST_NAMES_F if sex == "2" else S.FIRST_NAMES_M)
    surname = rng.choice(S.SURNAMES)
    title = ("Mrs" if rng.random() < 0.6 else "Ms") if sex == "2" else "Mr"
    outward, (imd_lo, imd_hi) = rng.choice(S.POSTCODE_OUTWARD)
    imd = rng.randint(imd_lo, imd_hi)
    practice_code, practice_name = rng.choice(S.PRACTICES)

    # --- the knee
    laterality = rng.choices(["Right", "Left", "Bilateral"], weights=[42, 38, 20])[0]
    icd10 = "M17.0" if laterality == "Bilateral" else "M17.1"
    kl = rng.choices([1, 2, 3, 4], weights=[4, 21, 43, 32])[0]
    # Oxford Knee Score (0-48, lower = worse). Listing-clinic mean ~17-19; referrals are spread wider.
    oks = int(round(clip(nrng.normal(31 - 3.6 * kl, 6.5), 2, 46)))
    months_between = rng.choice([3, 6, 6, 9, 12])
    decline = nrng.normal(1.5 + 0.6 * (kl - 2), 3.0) * (months_between / 6)
    oks_before = int(round(clip(oks + decline, oks - 4, 48)))

    # --- treatment tried (NICE NG226: exercise and weight advice first)
    physio_weeks = rng.choices([0, rng.randint(2, 5), rng.randint(6, 12), rng.randint(13, 20)], weights=[22, 15, 50, 13])[0]
    injections = rng.choices([0, 1, 2, 3], weights=[48, 30, 17, 5])[0]
    analgesia = rng.choice(["Paracetamol 1g QDS PRN", "Paracetamol 1g QDS", "Co-codamol 30/500 2 tablets QDS PRN",
                            "Naproxen 500mg BD with omeprazole 20mg OD", "Topical ibuprofen gel PRN"])

    # --- body and other conditions (NJR mean BMI for TKR ~31; diabetes rises with BMI)
    bmi = round(clip(nrng.lognormal(np.log(31), 0.17), 19, 55), 1)
    diabetes = rng.random() < clip(0.06 + 0.012 * (bmi - 25), 0.04, 0.45)
    hba1c = int(round(clip(nrng.normal(58, 9), 42, 95))) if diabetes else None
    hypertension = rng.random() < clip(0.25 + 0.006 * (age - 50), 0.15, 0.65)
    ckd = rng.random() < clip(0.03 + 0.004 * (age - 60), 0.01, 0.25)
    smoking = rng.choices(["Never smoked", "Ex-smoker", "Current smoker"], weights=[48, 40, 12])[0]

    # --- function and social context
    night_pain = rng.random() < clip(0.15 + 0.03 * (30 - oks), 0.05, 0.9)
    walking_aid = rng.random() < clip(0.1 + 0.035 * (28 - oks) + 0.01 * (age - 70), 0.03, 0.9)
    walk_minutes = int(clip(round(nrng.normal(5 + 1.2 * oks, 8)), 2, 90))
    lives_alone = rng.random() < clip(0.18 + 0.008 * (age - 65) + (0.08 if sex == "2" else 0), 0.08, 0.6)
    carer = (not lives_alone) and rng.random() < 0.11
    employed = age < 66 and rng.random() < 0.55

    # --- waiting list (assumption: T&O referral waits, median ~18 weeks, long tail past 52)
    weeks_waiting = int(clip(round(nrng.lognormal(np.log(18), 0.7)), 0, 104))
    referral_date = EXTRACT_DATE - timedelta(weeks=weeks_waiting, days=rng.randint(0, 6))
    priority = "2" if rng.random() < 0.06 else "1"

    p = {
        "patient_id": f"KP{i:05d}",
        "nhs_number": S.synthetic_nhs_number(rng, used_nhs),
        "title": title, "first_name": first, "surname": surname,
        "sex_code": sex, "sex": S.PERSON_STATED_GENDER[sex],
        "date_of_birth": dob.isoformat(), "age": age_on(dob),
        "postcode_outward": outward, "imd_decile": imd,
        "practice_code": practice_code, "practice_name": practice_name, "gp_name": rng.choice(S.GP_NAMES),
        "source_of_referral": "03", "priority_type": priority, "priority": S.PRIORITY_TYPE[priority],
        "treatment_function_code": "110", "rtt_status": "10",
        "referral_date": referral_date.isoformat(), "weeks_waiting": weeks_waiting,
        "icd10": icd10, "snomed_problem": S.SNOMED_KNEE_OA[0], "laterality": laterality,
        "kl_grade": kl, "oks": oks, "oks_before": oks_before, "oks_months_between": months_between,
        "physio_weeks": physio_weeks, "injections": injections, "analgesia": analgesia,
        "bmi": bmi, "diabetes": diabetes, "hba1c": hba1c, "hypertension": hypertension, "ckd": ckd,
        "smoking_status": smoking, "night_pain": night_pain, "walking_aid": walking_aid,
        "walk_minutes": walk_minutes, "lives_alone": lives_alone, "carer": carer, "employed": employed,
    }
    facts = {"oks": oks, "oks_before": oks_before, "kl": kl, "physio_weeks": physio_weeks, "bmi": bmi,
             "weeks_waiting": weeks_waiting, "night_pain": night_pain, "lives_alone_or_carer": lives_alone or carer}
    d = decide(facts)
    p["true_pathway"] = d["pathway"]
    p["true_pathway_label"] = PATHWAYS[d["pathway"]]
    p["true_rule"] = d["rule"]
    p["weight_support"] = d["weight_support"]
    p["priority_score"] = priority_score(facts)
    return p


# ---------------------------------------------------------------------------
# Data-quality problems for the raw file (section 3: cleaning)
# ---------------------------------------------------------------------------
def make_raw(clean: pd.DataFrame, rng: random.Random) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = clean.copy().astype(object)
    log = []

    def hit(share, field, fn, issue):
        idx = rng.sample(list(raw.index), int(len(raw) * share))
        for r in idx:
            old = raw.at[r, field]
            new = fn(old)
            if new is not old:
                raw.at[r, field] = new
                log.append({"row": r, "patient_id": raw.at[r, "patient_id"], "field": field,
                            "true_value": old, "raw_value": new, "issue": issue})

    hit(0.06, "oks", lambda v: None, "missing")
    hit(0.03, "bmi", lambda v: None, "missing")
    hit(0.02, "kl_grade", lambda v: None, "missing")
    hit(0.015, "bmi", lambda v: round(v * 10, 0), "decimal point lost (e.g. 31.4 -> 314)")
    hit(0.01, "age", lambda v: rng.choice([0, 129, 199]), "impossible value")
    hit(0.01, "oks", lambda v: v if v is None else rng.choice([52, 60, -1]), "out of range (OKS is 0-48)")
    hit(0.08, "laterality", lambda v: {"Right": rng.choice(["R", "Rt", "right"]), "Left": rng.choice(["L", "Lt", "left"]),
                                       "Bilateral": rng.choice(["Both", "B/L", "bilateral"])}[v], "inconsistent label")
    hit(0.10, "sex", lambda v: {"Male": rng.choice(["M", "male", "1"]), "Female": rng.choice(["F", "female", "2"])}[v],
        "inconsistent label")
    hit(0.05, "referral_date", lambda v: date.fromisoformat(v).strftime("%d/%m/%Y"), "mixed date format")
    hit(0.04, "smoking_status", lambda v: rng.choice(["", "unknown", v.upper()]), "inconsistent label")
    hit(0.03, "physio_weeks", lambda v: rng.choice(["some", "yes", "?", "6-8"]), "free text in numeric field")

    # duplicates: the same referral entered twice, sometimes with a slightly different name spelling
    dup_rows = rng.sample(list(raw.index), int(len(raw) * 0.012))
    dups = raw.loc[dup_rows].copy()
    for r in dups.index:
        if rng.random() < 0.5:
            dups.at[r, "surname"] = str(dups.at[r, "surname"]).upper()
        log.append({"row": r, "patient_id": dups.at[r, "patient_id"], "field": "(row)", "true_value": "",
                    "raw_value": "duplicate row", "issue": "duplicate referral"})
    raw = pd.concat([raw, dups]).sample(frac=1, random_state=rng.randint(0, 10_000)).reset_index(drop=True)
    # the raw file carries no answers: drop the derived truth columns
    raw = raw.drop(columns=["true_pathway", "true_pathway_label", "true_rule", "weight_support", "priority_score"])
    return raw, pd.DataFrame(log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    rng, nrng, used = random.Random(a.seed), np.random.default_rng(a.seed), set()
    clean = pd.DataFrame([make_patient(i + 1, rng, nrng, used) for i in range(a.n)])
    raw, log = make_raw(clean, rng)
    OUT.mkdir(parents=True, exist_ok=True)
    clean.to_csv(OUT / "patients_clean.csv", index=False)
    raw.to_csv(OUT / "patients_raw.csv", index=False)
    log.to_csv(OUT / "data_quality_log.csv", index=False)
    print(f"{len(clean):,} patients -> patients_clean.csv")
    print(f"{len(raw):,} rows (with duplicates and errors) -> patients_raw.csv; {len(log):,} issues logged")
    print(clean["true_pathway_label"].value_counts().to_string())


if __name__ == "__main__":
    main()
