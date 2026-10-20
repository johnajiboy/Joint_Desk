import pandas as pd
import pytest

from kneedss import clean as C

BASE = {
    "patient_id": "KP00001", "nhs_number": "999 000 0001", "title": "Mrs", "first_name": "Ann", "surname": "Hall",
    "sex_code": "2", "sex": "Female", "date_of_birth": "1955-03-01", "age": "71", "postcode_outward": "TS1",
    "imd_decile": "2", "practice_code": "Y99001", "practice_name": "Riverside", "gp_name": "Dr A. Patel",
    "source_of_referral": "3", "priority_type": "1", "priority": "Routine", "treatment_function_code": "110",
    "rtt_status": "10", "referral_date": "2026-06-23", "weeks_waiting": "17", "icd10": "M17.1",
    "snomed_problem": "239873007", "laterality": "Right", "kl_grade": "3.0", "oks": "20.0", "oks_before": "24",
    "oks_months_between": "6", "physio_weeks": "8", "injections": "1", "analgesia": "Paracetamol", "bmi": "31.4",
    "diabetes": "False", "hba1c": "", "hypertension": "False", "ckd": "False", "smoking_status": "Never smoked",
    "night_pain": "True", "walking_aid": "False", "walk_minutes": "30", "lives_alone": "False", "carer": "False",
    "employed": "False",
}


def run(*rows):
    df, actions = C.clean(pd.DataFrame([{**BASE, **r} for r in rows]))
    return df, actions


def one(**changes):
    df, actions = run(changes)
    return df.iloc[0], actions


def test_clean_row_needs_no_changes():
    r, actions = one()
    assert actions.empty
    assert r.age == 71 and r.weeks_waiting == 17 and r.oks == 20 and r.bmi == 31.4
    assert r.pathway == "surgery" and r.oks_band == "moderate to severe" and r.bmi_category == "Obese I"
    assert r.wait_band == "0-18 weeks"


@pytest.mark.parametrize("label,expected", [("R", "Right"), ("Rt", "Right"), ("left", "Left"), ("B/L", "Bilateral"),
                                            ("Both", "Bilateral")])
def test_laterality_labels(label, expected):
    assert one(laterality=label)[0].laterality == expected


def test_sex_follows_sex_code():
    r, actions = one(sex="2", sex_code="2")
    assert r.sex == "Female" and actions.action.tolist() == ["label standardised"]
    assert one(sex="m", sex_code="1")[0].sex == "Male"


def test_age_from_date_of_birth():
    r, actions = one(age="199")
    assert r.age == 71 and actions.action.tolist() == ["recalculated from date of birth"]


def test_mixed_date_format_and_weeks():
    r, _ = one(referral_date="23/06/2026")
    assert r.referral_date == "2026-06-23" and r.weeks_waiting == 17


def test_bmi_decimal_point_restored():
    r, actions = one(bmi="314.0")
    assert r.bmi == 31.4 and actions.action.tolist() == ["decimal point restored"]


def test_unrecoverable_values_set_missing_not_guessed():
    r, actions = one(oks="52.0", physio_weeks="6-8", smoking_status="unknown", kl_grade="")
    assert pd.isna(r.oks) and pd.isna(r.physio_weeks) and pd.isna(r.kl_grade) and r.smoking_status is None
    assert set(actions.action) == {"out of range, set missing", "free text in numeric field, set missing",
                                   "unknown, set missing"}
    assert r.pathway == "review"                     # missing facts: ask the GP


def test_smoking_capitals_standardised():
    assert one(smoking_status="EX-SMOKER")[0].smoking_status == "Ex-smoker"


def test_duplicate_keeps_the_row_not_in_capitals():
    df, actions = run({"surname": "HALL"}, {})
    assert len(df) == 1 and df.iloc[0].surname == "Hall"
    assert actions.action.tolist() == ["duplicate referral removed"]


@pytest.mark.parametrize("bmi,cat", [(18.4, "Underweight"), (18.5, "Healthy"), (29.9, "Overweight"),
                                     (30.0, "Obese I"), (35.0, "Obese II"), (40.0, "Obese III")])
def test_bmi_categories(bmi, cat):
    assert C.bmi_category(bmi) == cat


@pytest.mark.parametrize("weeks,b", [(0, "0-18 weeks"), (18, "0-18 weeks"), (19, "19-52 weeks"),
                                     (52, "19-52 weeks"), (53, "Over 52 weeks")])
def test_wait_bands(weeks, b):
    assert C.wait_band(weeks) == b


def test_real_raw_file_matches_the_log():
    """On the generated data: every logged problem is fixed or set missing, never left wrong."""
    root = C.ROOT / "data" / "output"
    raw = pd.read_csv(root / "patients_raw.csv", dtype=str, keep_default_na=False)
    truth = pd.read_csv(root / "patients_clean.csv").set_index("patient_id")
    log = pd.read_csv(root / "data_quality_log.csv")
    df, actions = C.clean(raw)
    clean = df.set_index("patient_id")
    assert len(df) == len(truth) and set(df.patient_id) == set(truth.index)
    for p, f, true in log[log.field != "(row)"][["patient_id", "field", "true_value"]].itertuples(index=False):
        got = clean.at[p, f]
        if not pd.isna(got):
            assert str(got) == str(true) or float(got) == float(true), (p, f, got, true)
    assert set(actions[actions.field == "(row)"].patient_id) == set(log[log.field == "(row)"].patient_id)
