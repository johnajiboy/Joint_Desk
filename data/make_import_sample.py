"""Make data/samples/import_sample.csv and .xlsx: 30 synthetic patients for the spreadsheet import demo.

Deliberately messy, like a real export: headers such as "NHS No", "Oxford score", "X-ray grade" and a typo
("Refferal date"), an extra "Notes" column, mixed date formats and labels. 10 rows update patients already on the
waiting list (newer scores), 17 are new referrals, and 3 rows are bad on purpose (an NHS number that fails the
check, an OKS of 55, an impossible date), so the import skips them with reasons.

    python data/make_import_sample.py
"""
from __future__ import annotations

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import standards as S          # noqa: E402

OUT = ROOT / "data" / "samples"
SEED = 909
HEADERS = ["NHS No", "Patient name", "DOB", "Gender", "Knee", "Oxford score", "Previous OKS", "X-ray grade",
           "BMI (kg/m2)", "Physio (weeks)", "Steroid injections", "Night pain?", "Lives alone / carer", "Walking aid",
           "Diabetic", "Smoker", "Refferal date", "Practice", "Notes"]


def fmt_date(d: date, rng: random.Random) -> str:
    return d.strftime("%d/%m/%Y") if rng.random() < 0.6 else d.isoformat()


def yes_no(v: bool, rng: random.Random) -> str:
    return rng.choice(["Y", "Yes", "yes"]) if v else rng.choice(["N", "No", "no"])


def main() -> None:
    rng = random.Random(SEED)
    wl = pd.read_csv(ROOT / "data" / "output" / "waiting_list.csv", dtype={"nhs_number": str})
    rows = []

    # 10 updates: patients already on the list, with a newer (worse) score
    for _, p in wl[wl.oks.notna() & wl.kl_grade.notna() & wl.physio_weeks.notna()].sample(10, random_state=SEED).iterrows():
        rows.append([p.nhs_number, f"{p.first_name} {p.surname}", fmt_date(date.fromisoformat(p.date_of_birth), rng),
                     rng.choice(["F", "Female"]) if p.sex == "Female" else rng.choice(["M", "Male"]),
                     rng.choice({"Right": ["Right", "Rt", "R"], "Left": ["Left", "Lt", "L"], "Bilateral": ["Both", "B/L"]}[p.laterality]),
                     int(max(0, p.oks - rng.randint(2, 6))), int(p.oks), int(p.kl_grade), "" if pd.isna(p.bmi) else p.bmi,
                     int(p.physio_weeks), int(p.injections), yes_no(bool(p.night_pain), rng),
                     yes_no(bool(p.lives_alone_or_carer), rng), yes_no(bool(p.walking_aid), rng), yes_no(bool(p.diabetes), rng),
                     (p.smoking_status or "").lower() if rng.random() < 0.3 else (p.smoking_status or ""),
                     fmt_date(date.fromisoformat(p.referral_date), rng), p.practice_code, "updated score from clinic"])

    # 17 new referrals
    used = set(wl.nhs_number)
    for i in range(17):
        sex = rng.choice(["Female", "Male"])
        first = rng.choice(S.FIRST_NAMES_F if sex == "Female" else S.FIRST_NAMES_M)
        kl = rng.choices([1, 2, 3, 4], weights=[5, 20, 45, 30])[0]
        oks = max(2, min(46, int(rng.gauss(31 - 3.6 * kl, 6))))
        dob = date(2026, 10, 20) - timedelta(days=int(rng.gauss(69, 9) * 365.25))
        referred = date(2026, 10, 20) - timedelta(weeks=rng.randint(0, 40), days=rng.randint(0, 6))
        rows.append([S.synthetic_nhs_number(rng, used), f"{first} {rng.choice(S.SURNAMES)}", fmt_date(dob, rng),
                     rng.choice(["F", "female"]) if sex == "Female" else rng.choice(["M", "male"]),
                     rng.choice(["Right", "left", "Rt", "Lt", "Both"]), oks if rng.random() > 0.1 else "",
                     "" if rng.random() < 0.5 else min(48, oks + rng.randint(0, 8)), kl,
                     round(rng.lognormvariate(3.43, 0.15), 1), rng.choice([0, 3, 6, 8, 12]), rng.choice([0, 0, 1, 2]),
                     yes_no(rng.random() < 0.5, rng), yes_no(rng.random() < 0.25, rng), yes_no(rng.random() < 0.3, rng),
                     yes_no(rng.random() < 0.12, rng), rng.choice(["Never smoked", "Ex-smoker", "current smoker"]),
                     fmt_date(referred, rng), rng.choice(S.PRACTICES)[0], "" if rng.random() < 0.7 else "new referral"])

    # 3 bad rows, each with one clear problem
    bad = [list(r) for r in rows[-3:]]
    bad[0][0] = "999 123 4567"           # fails the NHS number check
    bad[1][0] = S.synthetic_nhs_number(rng, used)
    bad[1][5] = 55                       # OKS outside 0-48
    bad[2][0] = S.synthetic_nhs_number(rng, used)
    bad[2][16] = "31/02/2026"            # no such date
    for r, note in zip(bad, ["bad NHS number", "OKS out of range", "impossible date"]):
        r[1] = r[1] + " (test)"
        r[18] = note
    rows += bad
    rng.shuffle(rows)

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "import_sample.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADERS)
        w.writerows(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "Referrals"
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    wb.save(OUT / "import_sample.xlsx")
    print(f"{len(rows)} rows -> data/samples/import_sample.csv and .xlsx (10 updates, 17 new, 3 bad)")


if __name__ == "__main__":
    main()
