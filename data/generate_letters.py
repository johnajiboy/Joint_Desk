"""Generate synthetic GP referral letters for knee osteoarthritis, each with an answer key.

    python data/generate_letters.py              # needs data/output/patients_clean.csv
    python data/generate_letters.py --n 150 --seed 11

Outputs (data/output/)
  letters/L0001.txt ...     one letter per file, as the clinic would receive it
  letters.jsonl             the same letters, one JSON object per line
  answer_key.jsonl          for each letter: the true facts AS STATED IN THE LETTER, the exact words each
                            fact comes from (evidence), difficulty tags and the gold pathway
  answer_key.csv            the same, flattened, for spreadsheets

Letters follow the shape of an NHS e-Referral Service referral: an auto-filled block from the GP record
(demographics, coded problems with SNOMED CT, medication, allergies, latest observations, results),
then the GP's free text. They are deliberately imperfect, as real letters are:
  - the Oxford Knee Score is often not recorded
  - X-ray findings are usually the radiologist's words, not a Kellgren-Lawrence grade
  - physiotherapy is sometimes vague, or written as "x8/52" (8 weeks)
  - BMI can appear twice, with a newer value in the free text
  - negations ("denies night pain"), four GP writing styles, initial and expedite letters

Gold-standard rule: a fact is only in the answer key if the letter states it (otherwise null). When
two values conflict, the most recent dated value is the gold one.
"""
from __future__ import annotations
import argparse, json, random, sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import standards as S           # noqa: E402
from kneedss.rules import decide, priority_score, PATHWAYS   # noqa: E402

OUT = ROOT / "data" / "output"
WORDS = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
         9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 14: "fourteen", 16: "sixteen", 20: "twenty"}
FIELDS = ["name", "age", "sex", "side", "oks", "oks_before", "kl", "xray_finding", "physio_weeks", "injections",
          "bmi", "night_pain", "lives_alone_or_carer", "walking_aid", "diabetes", "smoking", "weeks_waiting"]


def ddmmyyyy(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


class Letter:
    """Builds the text while recording, for each fact, the exact words it came from."""

    def __init__(self):
        self.blocks: list[str] = []
        self.gold = {f: None for f in FIELDS}
        self.evidence: dict[str, str] = {}
        self.tags: set[str] = set()

    def add(self, text: str):
        self.blocks.append(text)

    def fact(self, field: str, value, quote: str | None):
        self.gold[field] = value
        if quote:
            self.evidence[field] = quote

    def text(self) -> str:
        t = "\n".join(self.blocks).rstrip() + "\n"
        for f, q in self.evidence.items():
            assert q in t, f"evidence for {f} not in letter: {q!r}"
        return t


def build(p: pd.Series, n: int, rng: random.Random) -> tuple[str, dict]:
    L = Letter()
    expedite = p.weeks_waiting >= 20 and rng.random() < 0.45
    letter_type = "expedite" if expedite else "initial"
    style = rng.choices(["structured", "narrative", "brief"], weights=[35, 40, 25])[0]
    ref_date = date.fromisoformat(p.referral_date)
    letter_date = (ref_date + timedelta(weeks=int(p.weeks_waiting), days=-rng.randint(0, 10))) if expedite else ref_date
    dob = date.fromisoformat(p.date_of_birth)
    age = age_on(dob, letter_date)
    pronoun, obj, poss = ("She", "her", "her") if p.sex == "Female" else ("He", "him", "his")
    title_name = f"{p.title} {p.first_name} {p.surname}"
    side = p.laterality.lower()
    knee_words = "both knees" if side == "bilateral" else f"{side} knee"
    the_knee = "both knees" if side == "bilateral" else f"the {side} knee"

    # ------------------------------------------------------------ auto-filled block (from the GP record)
    obs_date = letter_date - timedelta(days=rng.randint(10, 200))
    bmi_coded = p.bmi if rng.random() < 0.85 else round(p.bmi + rng.choice([-2.4, -1.6, 1.8, 2.6]), 1)
    hdr = [
        "NHS e-Referral Service - Referral letter",
        "SYNTHETIC TEST DATA - NOT A REAL PATIENT",
        "",
        f"Service: Trauma and Orthopaedics - MSK Triage (Knee)     Treatment function: 110",
        f"Priority: {p.priority}     Referral date: {ddmmyyyy(letter_date)}     UBRN: 0000 {rng.randint(1000,9999)} {rng.randint(1000,9999)}",
        "",
        f"Patient: {p.title} {p.first_name} {p.surname.upper()}     DOB: {ddmmyyyy(dob)}     Gender: {p.sex}",
        f"NHS No: {p.nhs_number}     Postcode: {p.postcode_outward} (outward code only)",
        f"Registered practice: {p.practice_name} ({p.practice_code})     Referring clinician: {p.gp_name}",
        "",
        "Problems",
        f"  Osteoarthritis of knee (SNOMED CT {S.SNOMED_KNEE_OA[0]}) - {letter_date.year - rng.randint(1, 6)}",
    ]
    if p.diabetes:
        hdr.append(f"  Type 2 diabetes mellitus (SNOMED CT {S.COMORBIDITY_SNOMED['Type 2 diabetes mellitus']}) - {letter_date.year - rng.randint(2, 15)}")
    if p.hypertension:
        hdr.append(f"  Essential hypertension (SNOMED CT {S.COMORBIDITY_SNOMED['Essential hypertension']}) - {letter_date.year - rng.randint(2, 20)}")
    if p.ckd:
        hdr.append(f"  Chronic kidney disease stage 3 (SNOMED CT {S.COMORBIDITY_SNOMED['Chronic kidney disease']})")
    meds = [p.analgesia]
    if p.diabetes: meds.append("Metformin 500mg BD")
    if p.hypertension: meds.append(rng.choice(["Amlodipine 5mg OD", "Ramipril 5mg OD", "Losartan 50mg OD"]))
    hdr += ["Medication"] + [f"  {m}" for m in meds]
    hdr += ["Allergies", "  " + rng.choice(["No known drug allergies", "No known drug allergies", "Penicillin - rash", "Codeine - nausea"])]
    bmi_line = f"BMI {bmi_coded} kg/m2 ({ddmmyyyy(obs_date)})"
    smoke_line = f"Smoking status: {p.smoking_status}"
    hdr += ["Latest observations", f"  {bmi_line}", f"  {smoke_line}"]
    if p.diabetes:
        hdr += ["Recent results", f"  HbA1c {int(p.hba1c)} mmol/mol ({ddmmyyyy(obs_date)})"]
    hdr += ["", "-" * 72, ""]
    L.add("\n".join(hdr))
    L.fact("name", f"{p.first_name} {p.surname}", f"{p.first_name} {p.surname.upper()}")
    L.fact("sex", p.sex, f"Gender: {p.sex}")
    L.fact("age", age, f"DOB: {ddmmyyyy(dob)}")
    L.fact("bmi", bmi_coded, bmi_line)
    L.fact("smoking", p.smoking_status, smoke_line)
    L.fact("diabetes", bool(p.diabetes), "Type 2 diabetes mellitus" if p.diabetes else None)
    if bmi_coded != p.bmi:
        L.tags.add("bmi_conflict")

    # ------------------------------------------------------------ free text
    greet = rng.choice(["Dear Orthopaedic Colleague,", "Dear Colleague,", "Dear MSK Triage Team,", "Dear Doctor,"])
    say_age = rng.random() < 0.6
    intro_age = f", aged {age}" if say_age else ""
    if expedite:
        opener = (f"I am writing again about {title_name}{intro_age}, who is on your waiting list with osteoarthritis of {the_knee}. "
                  f"{pronoun} has deteriorated since the original referral and I would be grateful if {poss} care could be expedited.")
    else:
        opener = rng.choice([
            f"Thank you for seeing {title_name}{intro_age}, with osteoarthritis of {the_knee}.",
            f"I would be grateful for your assessment of {title_name}{intro_age}, who has worsening pain in {the_knee}.",
            f"Re: {title_name}{intro_age}. Knee osteoarthritis, {knee_words}, for opinion regarding further management.",
        ])
    side_quote = knee_words
    L.fact("side", p.laterality, side_quote)

    sents: dict[str, list[str]] = {"history": [], "imaging": [], "treatment": [], "social": [], "request": []}

    # Oxford Knee Score: recorded in ~80% of letters
    if rng.random() < 0.8:
        form = rng.choice(["Her Oxford Knee Score today is {o}", "Oxford Knee Score {o}", "OKS {o}/48", "Oxford knee score recorded at {o}"])
        form = form.replace("Her ", f"{poss.capitalize()} ")
        q = form.format(o=int(p.oks))
        if rng.random() < 0.65:
            before_q = rng.choice([f"down from {int(p.oks_before)} {int(p.oks_months_between)} months ago",
                                   f"(previously {int(p.oks_before)})", f"compared with {int(p.oks_before)} at the last review"])
            sep = " " if before_q.startswith("(") else ", "
            sents["history"].append(f"{q}{sep}{before_q}.")
            L.fact("oks_before", int(p.oks_before), before_q)
        else:
            sents["history"].append(f"{q}.")
        L.fact("oks", int(p.oks), q)
    else:
        L.tags.add("oks_missing")
        if rng.random() < 0.4:
            sents["history"].append("I have not recorded a formal Oxford Knee Score.")

    # pain and function (free description, not a gold fact except walking aid)
    sents["history"].append(rng.choice([
        f"{pronoun} can walk for about {int(p.walk_minutes)} minutes before needing to stop.",
        f"Walking tolerance is around {int(p.walk_minutes)} minutes.",
        f"{pronoun} struggles with stairs and can manage roughly {int(p.walk_minutes)} minutes on the flat."]))
    r = rng.random()
    if r < 0.75:
        if p.night_pain:
            q = rng.choice(["night pain most nights", "Pain wakes her at night".replace("her", obj), "disturbed sleep due to knee pain"])
            sents["history"].append(f"{pronoun} reports {q}." if not q.startswith("Pain") else f"{q}.")
            L.fact("night_pain", True, q)
        else:
            q = rng.choice(["No night pain", "denies night pain", "sleeps well"])
            sents["history"].append(f"{q.capitalize() if q[0].islower() else q}.")
            L.fact("night_pain", False, q.capitalize() if q[0].islower() else q)
            L.tags.add("negation")
    if rng.random() < 0.7:
        if p.walking_aid:
            q = rng.choice(["uses a walking stick", "now mobilises with a stick", "uses a frame outdoors"])
            sents["history"].append(f"{pronoun} {q}.")
            L.fact("walking_aid", True, q)
        else:
            q = "walks without aids"
            sents["history"].append(f"{pronoun} {q}.")
            L.fact("walking_aid", False, q)

    # Imaging: KL stated (25%), radiologist wording only (65%), requested (5%), not mentioned (5%)
    xr = rng.choices(["kl", "wording", "requested", "none"], weights=[25, 65, 5, 5])[0]
    xdate = ddmmyyyy(letter_date - timedelta(days=rng.randint(20, 300)))
    wording = rng.choice(S.KL_REPORT_WORDING[int(p.kl_grade)])
    if xr == "kl":
        q = rng.choice([f"Kellgren-Lawrence grade {int(p.kl_grade)}", f"KL grade {int(p.kl_grade)}", f"KL{int(p.kl_grade)}"])
        sents["imaging"].append(f"X-ray ({xdate}): {wording[:-1]}, {q}.")
        L.fact("kl", int(p.kl_grade), q)
        L.fact("xray_finding", wording[:-1], wording[:-1])
    elif xr == "wording":
        sents["imaging"].append(f'X-ray report ({xdate}): "{wording}"')
        L.fact("kl", int(p.kl_grade), wording)            # the reader must turn the words into a grade
        L.fact("xray_finding", wording, wording)
        L.tags.add("kl_from_wording")
    elif xr == "requested":
        sents["imaging"].append("An X-ray has been requested but not yet reported.")
        L.tags.add("xray_missing")
    else:
        L.tags.add("xray_missing")

    # Physiotherapy: weeks (86%), vague (8%), not mentioned (6%)
    pr = rng.choices(["weeks", "vague", "none"], weights=[86, 8, 6])[0]
    pw = int(p.physio_weeks)
    if pr == "weeks":
        if pw == 0:
            q = rng.choice(["has not yet had physiotherapy", "no physiotherapy to date"])
            sents["treatment"].append(f"{pronoun} {q}." if q.startswith("has") else f"There has been {q}.")
        elif style == "brief" and rng.random() < 0.6:
            q = f"physio x{pw}/52"
            sents["treatment"].append(f"Failed conservative mx incl. {q}.")
            L.tags.add("abbreviation")
        else:
            wk = WORDS.get(pw, str(pw)) if rng.random() < 0.35 else str(pw)
            q = f"{wk} weeks of physiotherapy"
            sents["treatment"].append(rng.choice([f"{pronoun} has completed {q} with limited benefit.",
                                                  f"{pronoun} has had {q} in the community.",
                                                  f"Management to date has included {q}."]))
        L.fact("physio_weeks", pw, q)
    elif pr == "vague":
        sents["treatment"].append(rng.choice([f"{pronoun} has had some physiotherapy in the past but I do not have the details.",
                                              f"{pronoun} tells me {pronoun.lower()} saw a physiotherapist a while ago."]))
        L.tags.add("physio_vague")
    else:
        L.tags.add("physio_missing")

    if rng.random() < 0.8:
        k = int(p.injections)
        if k == 0:
            q = rng.choice(["no steroid injections", "has not had any injections"])
            sents["treatment"].append(f"There have been {q}." if q.startswith("no") else f"{pronoun} {q}.")
        else:
            q = f"{WORDS[k]} steroid injection{'s' if k > 1 else ''}" if rng.random() < 0.6 else f"{k} intra-articular steroid injection{'s' if k > 1 else ''}"
            sents["treatment"].append(f"{pronoun} has had {q}, with only short-lived relief.")
        L.fact("injections", k, q)
    sents["treatment"].append(f"Current analgesia: {p.analgesia}.")

    # BMI updated in free text (newer than the coded value) in ~12% of letters
    if rng.random() < 0.12 or bmi_coded != p.bmi:
        q = f"BMI today {p.bmi}"
        sents["treatment"].append(f"Weighed in clinic, {q}.")
        L.fact("bmi", float(p.bmi), q)            # newest dated value wins
        L.tags.add("bmi_two_values")

    # Social context
    if rng.random() < 0.75:
        if p.lives_alone:
            q = "lives alone"
            sents["social"].append(f"{pronoun} {q}" + rng.choice([" and is finding it hard to cope.", "."]))
            L.fact("lives_alone_or_carer", True, q)
        elif p.carer:
            q = rng.choice(["main carer for her husband", "cares for her grandchildren several days a week"]) if p.sex == "Female" \
                else rng.choice(["main carer for his wife", "cares for his elderly mother"])
            sents["social"].append(f"{pronoun} is the {q}." if q.startswith("main") else f"{pronoun} {q}.")
            L.fact("lives_alone_or_carer", True, q)
        else:
            q = rng.choice(["lives with family", "lives with her partner".replace("her", poss)])
            sents["social"].append(f"{pronoun} {q}.")
            L.fact("lives_alone_or_carer", False, q)
    if p.employed and rng.random() < 0.6:
        sents["social"].append(f"{pronoun} works and the knee is affecting {poss} job.")

    # Waiting time: stated in expedite letters only
    if expedite:
        q = rng.choice([f"on your waiting list for {int(p.weeks_waiting)} weeks", f"waiting {int(p.weeks_waiting)} weeks"])
        sents["request"].append(f"{pronoun} has now been {q}." if q.startswith("on") else f"{pronoun} has been {q} so far.")
        L.fact("weeks_waiting", int(p.weeks_waiting), q)
    sents["request"].append(rng.choice([f"{pronoun} would like to discuss knee replacement.",
                                        f"I would be grateful for your opinion regarding further management.",
                                        f"{pronoun} is keen to consider surgery if appropriate."]))

    # ------------------------------------------------------------ assemble in the chosen style
    L.add(greet)
    L.add("")
    L.add(opener)
    L.add("")
    if style == "structured":
        for head, key in [("History", "history"), ("Imaging", "imaging"), ("Management to date", "treatment"),
                          ("Social", "social"), ("Request", "request")]:
            if sents[key]:
                L.add(f"{head}: " + " ".join(sents[key]))
                L.add("")
    elif style == "brief":
        for key in ["history", "imaging", "treatment", "social", "request"]:
            for s in sents[key]:
                L.add(f"- {s}")
        L.add("")
    else:
        for key in ["history", "imaging", "treatment", "social", "request"]:
            if sents[key]:
                L.add(" ".join(sents[key]))
                L.add("")
    L.add(rng.choice(["Yours sincerely,", "Kind regards,", "With thanks,", "Best wishes,"]))
    L.add(p.gp_name)
    L.add(p.practice_name)
    text = L.text()

    # ------------------------------------------------------------ gold decisions
    g = L.gold
    letter_facts = {"oks": g["oks"], "oks_before": g["oks_before"], "kl": g["kl"], "physio_weeks": g["physio_weeks"],
                    "bmi": g["bmi"], "weeks_waiting": int(p.weeks_waiting), "night_pain": g["night_pain"],
                    "lives_alone_or_carer": g["lives_alone_or_carer"]}
    d = decide(letter_facts)
    key = {
        "letter_id": f"L{n:04d}", "patient_id": p.patient_id, "letter_type": letter_type, "style": style,
        "letter_date": letter_date.isoformat(), "difficulty_tags": sorted(L.tags),
        "gold": g, "evidence": L.evidence,
        "gold_pathway": d["pathway"], "gold_pathway_label": PATHWAYS[d["pathway"]], "gold_rule": d["rule"],
        "gold_weight_support": d["weight_support"], "gold_priority_score": priority_score(letter_facts),
        "record_pathway": p.true_pathway,          # what the full GP record would give: shows the cost of missing facts
    }
    return text, key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    pts = pd.read_csv(OUT / "patients_clean.csv")
    # stratify by pathway so every pathway is well represented
    per = {"surgery": 0.45, "non_surgical": 0.22, "physio": 0.20, "weight_physio": 0.13}
    picks = []
    for k, share in per.items():
        pool = pts[pts.true_pathway == k]
        picks.append(pool.sample(n=min(len(pool), round(a.n * share)), random_state=a.seed))
    sample = pd.concat(picks).sample(frac=1, random_state=a.seed).head(a.n).reset_index(drop=True)

    (OUT / "letters").mkdir(parents=True, exist_ok=True)
    keys, rows = [], []
    with open(OUT / "letters.jsonl", "w") as fl, open(OUT / "answer_key.jsonl", "w") as fk:
        for i, p in sample.iterrows():
            text, key = build(p, i + 1, rng)
            (OUT / "letters" / f"{key['letter_id']}.txt").write_text(text)
            fl.write(json.dumps({"letter_id": key["letter_id"], "text": text}) + "\n")
            fk.write(json.dumps(key, default=str) + "\n")
            flat = {k: v for k, v in key.items() if k not in ("gold", "evidence")}
            flat["difficulty_tags"] = ";".join(key["difficulty_tags"])
            flat.update({f"gold_{f}": key["gold"][f] for f in FIELDS})
            flat.update({f"evidence_{f}": key["evidence"].get(f) for f in FIELDS})
            rows.append(flat)
    pd.DataFrame(rows).to_csv(OUT / "answer_key.csv", index=False)
    df = pd.DataFrame(rows)
    print(f"{len(df)} letters -> letters/, letters.jsonl, answer_key.jsonl, answer_key.csv")
    print(df.gold_pathway_label.value_counts().to_string())


if __name__ == "__main__":
    main()
