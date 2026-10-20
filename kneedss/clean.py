"""Clean the raw waiting-list extract (patients_raw.csv) into one row per patient.

Every change is written to an actions table (patient, field, raw value, clean value, action), so each fix can be
checked against data_quality_log.csv. Values that can be recovered from another field are recovered (sex from the
sex code, age from the date of birth, a lost BMI decimal point); values that can't are set to missing rather than
guessed. The rules (rules.py) then give each patient a pathway and priority, and OKS, BMI and wait are banded.

    python -m kneedss.clean     -> data/output/waiting_list.csv, data/output/cleaning_actions.csv
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from kneedss.rules import PATHWAYS, decide, priority_score
from kneedss.standards import oks_band

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "output"
EXTRACT_DATE = date(2026, 10, 20)          # date of the extract (see docs/data_dictionary.md)

SEX = {"1": "Male", "m": "Male", "male": "Male", "2": "Female", "f": "Female", "female": "Female"}
SEX_CODE = {"1": "Male", "2": "Female"}
LATERALITY = {"r": "Right", "rt": "Right", "right": "Right", "l": "Left", "lt": "Left", "left": "Left",
              "b/l": "Bilateral", "both": "Bilateral", "bilateral": "Bilateral"}
SMOKING = {"never smoked": "Never smoked", "ex-smoker": "Ex-smoker", "current smoker": "Current smoker"}
RANGES = {"oks": (0, 48), "oks_before": (0, 48), "kl_grade": (0, 4), "bmi": (12, 80), "age": (16, 110),
          "physio_weeks": (0, 104)}

# BMI categories (WHO adult), and waiting-time bands at the 18-week RTT standard and the 52-week long-wait mark.
BMI_CATEGORIES = [(0, 18.5, "Underweight"), (18.5, 25, "Healthy"), (25, 30, "Overweight"), (30, 35, "Obese I"),
                  (35, 40, "Obese II"), (40, 999, "Obese III")]
WAIT_BANDS = [(0, 18, "0-18 weeks"), (19, 52, "19-52 weeks"), (53, 999, "Over 52 weeks")]

INT_COLS = ["age", "imd_decile", "weeks_waiting", "kl_grade", "oks", "oks_before", "oks_months_between",
            "physio_weeks", "injections", "hba1c", "walk_minutes", "sex_code", "priority_type",
            "source_of_referral", "treatment_function_code", "rtt_status", "snomed_problem"]
BOOL_COLS = ["diabetes", "hypertension", "ckd", "night_pain", "walking_aid", "lives_alone", "carer", "employed"]


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() == ""


def _num(v) -> float | None:
    """A number, or None for blanks and free text ("some", "6-8", "?")."""
    if _blank(v):
        return None
    s = str(v).strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def _date(v) -> str | None:
    """ISO date from ISO or dd/mm/yyyy."""
    if _blank(v):
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return pd.to_datetime(s, format=fmt).date().isoformat()
        except ValueError:
            pass
    return None


def age_on(dob: str, on: date = EXTRACT_DATE) -> int:
    b = date.fromisoformat(dob)
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


def wait_band(weeks) -> str | None:
    if _blank(weeks) or pd.isna(weeks):
        return None
    return next(name for lo, hi, name in WAIT_BANDS if lo <= weeks <= hi)


def bmi_category(bmi) -> str | None:
    if _blank(bmi) or pd.isna(bmi):
        return None
    return next(name for lo, hi, name in BMI_CATEGORIES if lo <= bmi < hi)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(clean table, actions). Raw columns are read as text so nothing is coerced silently."""
    df = raw.astype(object).where(raw.notna(), None).copy()
    actions: list[dict] = []

    def act(i, field, new, action):
        old = df.at[i, field]
        if not (_blank(old) and _blank(new)) and str(old) != str(new):
            actions.append({"patient_id": df.at[i, "patient_id"], "field": field, "raw_value": old,
                            "clean_value": new, "action": action})
        df.at[i, field] = new

    # 1. duplicate referrals: same NHS number twice. Keep the row whose surname isn't in capitals (a re-keyed copy).
    df["_caps"] = df.surname.map(lambda s: str(s).isupper())
    df = df.sort_values(["nhs_number", "_caps"], kind="stable")
    dup = df.nhs_number.duplicated(keep="first")
    for i in df.index[dup]:
        actions.append({"patient_id": df.at[i, "patient_id"], "field": "(row)", "raw_value": "duplicate row",
                        "clean_value": "", "action": "duplicate referral removed"})
    df = df[~dup].drop(columns="_caps")

    for i in df.index:
        r = df.loc[i]
        # 2. labels
        code = str(r.sex_code).strip()
        sex = SEX_CODE.get(code) or SEX.get(str(r.sex).strip().lower())
        act(i, "sex", sex, "label standardised" if sex else "unknown label, set missing")
        side = LATERALITY.get(str(r.laterality).strip().lower())
        act(i, "laterality", side, "label standardised" if side else "unknown label, set missing")
        smoke = SMOKING.get(str(r.smoking_status).strip().lower()) if not _blank(r.smoking_status) else None
        act(i, "smoking_status", smoke, "label standardised" if smoke else "unknown, set missing")

        # 3. dates, and the values that follow from them
        for field in ("referral_date", "date_of_birth"):
            d = _date(r[field])
            act(i, field, d, "date format standardised" if d else "unreadable date, set missing")
        if df.at[i, "date_of_birth"]:
            act(i, "age", age_on(df.at[i, "date_of_birth"]), "recalculated from date of birth")
        if df.at[i, "referral_date"]:
            weeks = (EXTRACT_DATE - date.fromisoformat(df.at[i, "referral_date"])).days // 7
            act(i, "weeks_waiting", weeks, "recalculated from referral date")

        # 4. numbers
        bmi = _num(r.bmi)
        if bmi is not None and bmi > RANGES["bmi"][1] and RANGES["bmi"][0] <= bmi / 10 <= RANGES["bmi"][1]:
            act(i, "bmi", round(bmi / 10, 1), "decimal point restored")
        for field in ("oks", "oks_before", "kl_grade", "physio_weeks", "bmi"):
            v = _num(df.at[i, field])
            if v is None and not _blank(df.at[i, field]):
                act(i, field, None, "free text in numeric field, set missing")
            elif v is not None and not (RANGES[field][0] <= v <= RANGES[field][1]):
                act(i, field, None, "out of range, set missing")

    # 5. types
    for c in INT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").round().astype("Int64")
    df["bmi"] = pd.to_numeric(df["bmi"], errors="coerce").astype(float)
    for c in BOOL_COLS:
        df[c] = df[c].map(lambda v: None if _blank(v) else str(v).strip().lower() in ("true", "1", "yes"))
    df["sex_code"] = df.sex.map({"Male": 1, "Female": 2}).astype("Int64")
    df["lives_alone_or_carer"] = [bool(a) or bool(c) for a, c in zip(df.lives_alone, df.carer)]

    # 6. bands
    df["oks_band"] = df.oks.map(lambda v: None if pd.isna(v) else oks_band(int(v)))
    df["bmi_category"] = df.bmi.map(bmi_category)
    df["wait_band"] = df.weeks_waiting.map(wait_band)

    # 7. rules: pathway and priority from the cleaned facts (missing facts send the referral back to the GP)
    def facts(r):
        f = {"oks": r.oks, "oks_before": r.oks_before, "kl": r.kl_grade, "physio_weeks": r.physio_weeks,
             "bmi": r.bmi, "weeks_waiting": r.weeks_waiting, "night_pain": r.night_pain,
             "lives_alone_or_carer": r.lives_alone_or_carer}
        return {k: (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)) for k, v in f.items()}

    decisions = [decide(facts(r)) for r in df.itertuples()]
    df["pathway"] = [d["pathway"] for d in decisions]
    df["pathway_label"] = df.pathway.map(PATHWAYS)
    df["rule"] = [d["rule"] for d in decisions]
    df["weight_support"] = [d["weight_support"] for d in decisions]
    df["priority_score"] = [priority_score(facts(r)) for r in df.itertuples()]

    df = df.sort_values("patient_id").reset_index(drop=True)
    return df, pd.DataFrame(actions, columns=["patient_id", "field", "raw_value", "clean_value", "action"])


def main() -> None:
    raw = pd.read_csv(OUT / "patients_raw.csv", dtype=str, keep_default_na=False)
    df, actions = clean(raw)
    df.to_csv(OUT / "waiting_list.csv", index=False)
    actions.to_csv(OUT / "cleaning_actions.csv", index=False)
    print(f"{len(raw):,} raw rows -> {len(df):,} patients (waiting_list.csv); {len(actions):,} changes "
          f"(cleaning_actions.csv)")
    print(actions.groupby(["field", "action"]).size().to_string())


if __name__ == "__main__":
    main()
