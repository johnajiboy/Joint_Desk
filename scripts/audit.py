"""Audit Joint Desk against its five core claims and write docs/audit.md. No API calls; changes no behaviour.

Runs against a throwaway database with DEMO_MODE=1. Every code reference is found in the source at run time,
so the file:line links stay right.

    python scripts/audit.py        (needs the exported letters: python scripts/export_pdfs.py)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/audit.db"
os.environ["DEMO_MODE"] = "1"
os.environ["UPLOAD_PASSCODE"] = ""          # blank, not missing: .env can't switch the passcode on for this run

from fastapi.testclient import TestClient    # noqa: E402
from sqlmodel import Session, select         # noqa: E402

from backend import services as S           # noqa: E402
from backend.db import Decision, Patient, get_engine   # noqa: E402
from backend.main import app                 # noqa: E402
from kneedss import extract as X             # noqa: E402
from kneedss import optimise as O            # noqa: E402
from kneedss.rules import PATHWAYS, decide   # noqa: E402
from kneedss.schemas import LetterFacts      # noqa: E402

OUT = ROOT / "data" / "output"
md: list[str] = []
verdicts: list[tuple[str, bool, str]] = []
FACTS = [("oks", "OKS"), ("kl", "KL grade"), ("physio_weeks", "Physio weeks"), ("bmi", "BMI")]


def where(path: str, pattern: str) -> str:
    """`path:line` of the first line matching pattern, with the line itself."""
    for i, line in enumerate((ROOT / path).read_text().splitlines(), 1):
        if re.search(pattern, line):
            return f"`{path}:{i}` `{line.strip()}`"
    raise AssertionError(f"{pattern!r} not found in {path}")


def check(ok: bool, what: str) -> bool:
    md.append(f"- {'✓' if ok else '✗ FAIL'} {what}")
    return ok


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def table(head: list[str], rows: list[list]) -> list[str]:
    cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]


with TestClient(app) as c:
    # ------------------------------------------------------------------ 1. reading
    md += ["## 1. Reading: PDF, DOCX and TXT through POST /letters (DEMO_MODE=1)", "",
           "Code: " + where("backend/main.py", r'@app.post\("/letters"'),
           "; " + where("kneedss/extract.py", r"^def read_letter"),
           "; " + where("backend/services.py", r"^def read_letter"),
           "; " + where("backend/services.py", r"all\(X.quote_in_letter\(q, text\)"), ""]
    files = [
        ("L0010.pdf", zipfile.ZipFile(OUT / "letters_pdf.zip").read("L0010.pdf")),
        ("T0003.docx", zipfile.ZipFile(OUT / "letters_docx_sample.zip").read("T0003.docx")),
        ("L0011.txt", (OUT / "letters" / "L0011.txt").read_bytes()),
    ]
    results = c.post("/letters", files=[("files", (n, d, "application/octet-stream")) for n, d in files]).json()
    ok1 = check(len(results) == 3 and all(r["ok"] for r in results), "all three files read (one request, DEMO_MODE=1, no API call)")
    rows = []
    for r in results:
        p = c.get(f"/patients/{r['referral']['id']}").json()
        for key, label in FACTS:
            q = p["quotes"].get(key)
            rows.append([r["file"], p["name"], label, p["facts"].get(key), q or "—",
                         "yes" if q and X.quote_in_letter(q, p["letter_text"]) else ("n/a" if p["facts"].get(key) is None else "NO")])
        ok1 &= check(all(X.quote_in_letter(q, p["letter_text"]) for q in p["quotes"].values()),
                     f"{r['file']}: every one of {len(p['quotes'])} quotes is in the text read from the file")
    md += [""] + table(["File", "Patient", "Fact", "Value", "Exact quote", "Quote in file"], rows) + [""]
    verdicts.append(("Reading", ok1, "3/3 files (PDF, DOCX, TXT) read; OKS, KL, physio, BMI each with a quote found in the file"))

    # ------------------------------------------------------------------ 2. quote check
    md += ["## 2. Quote check drops an invented quote", "",
           "Code: " + where("kneedss/extract.py", r"^def check_quotes") + "; " + where("kneedss/extract.py", r'reason = "quote not in letter"'), ""]
    text = (OUT / "letters" / "L0001.txt").read_text()
    raw = json.loads(X.cache_path("L0001").read_text())["raw"]
    fake = json.loads(json.dumps(raw))
    fake["oks"] = {"value": 12, "quote": "Her Oxford Knee Score today is 12"}     # invented: the letter says 22
    facts, quotes, dropped = X.check_quotes(fake, text)
    real_kept = [f for f in ("kl", "physio_weeks", "bmi", "oks_before", "night_pain") if facts[f] == raw[f]["value"] and f in quotes]
    ok2 = check(facts["oks"] is None and "oks" not in quotes, "invented OKS 12 dropped: facts['oks'] is None, no quote kept")
    ok2 &= check(dropped == [{"field": "oks", "value": 12, "quote": "Her Oxford Knee Score today is 12", "reason": "quote not in letter"}],
                 f"recorded as dropped: `{dropped}`")
    ok2 &= check(len(real_kept) == 5, f"real facts kept with their quotes: {', '.join(f'{f}={facts[f]!r}' for f in real_kept)}")
    ok2 &= check(X.check_quotes(raw, text)[2] == [], "control: the real answer for L0001 drops nothing")
    md += [""]
    verdicts.append(("Quote check", ok2, "invented OKS quote dropped and logged with reason 'quote not in letter'; 5 real facts kept"))

    # ------------------------------------------------------------------ 3. rules decide
    md += ["## 3. The rules decide, not the LLM", "",
           "Code: " + where("kneedss/schemas.py", r"^class LetterFacts") + "; " + where("kneedss/extract.py", r"d = decide\(f\)")
           + "; " + where("backend/services.py", r"dec = X.decide_letter") + "; " + where("kneedss/importer.py", r"d = decide\(f\)"), ""]
    schema_fields = list(LetterFacts.model_fields)
    ok3 = check(not any(re.search(r"pathway|priority|rule|decision", f) for f in schema_fields),
                f"LLM schema fields ({len(schema_fields)}): {', '.join(schema_fields)}; no pathway, priority or rule")
    calls = run(["grep", "-rn", "llm.complete_json(", "kneedss", "backend", "scripts", "eval", "--include=*.py"]).splitlines()
    calls = [u for u in calls if not u.startswith("scripts/audit.py")]
    ok3 &= check(len(calls) == 1 and calls[0].startswith("kneedss/extract.py"),
                 f"the LLM is called in one place only: `{':'.join(calls[0].split(':')[:2])}` "
                 f"`{':'.join(calls[0].split(':')[2:]).strip()}`; its answer is validated as LetterFacts (facts only)")
    setters = run(["grep", "-rnE", r'\bp\.pathway\b[^=]*= *(dec|d|p)\[|pathway=(dec|d)\[|\.new_pathway if d else',
                   "backend", "kneedss", "--include=*.py"]).splitlines()
    from_rules = all(re.search(r'= *(dec|d)\[|pathway=(dec|d)\[|new_pathway if d else|= *p\["pathway"\]', x) for x in setters)
    ok3 &= check(bool(setters) and from_rules, "every place a stored pathway is set takes it from rules output (`d`/`dec` = decide() / "
                 "decide_letter() / importer.classify()), the seeded demo letters (computed by decide_letter), or a clinician Decision:")
    md += [f"  - `{':'.join(x.split(':')[:2])}` `{':'.join(x.split(':')[2:]).strip()}`" for x in setters]
    examples = []
    keys = [json.loads(line) for line in open(OUT / "answer_key.jsonl")]
    for want in ("surgery", "physio", "review"):
        k = next(k for k in keys if k["gold_pathway"] == want)
        ex = X.extract((OUT / "letters" / f"{k['letter_id']}.txt").read_text(), k["letter_id"])
        weeks = c.get(f"/patients/{k['patient_id']}").json()["weeks_waiting"]
        f = {"oks": ex.facts["oks"], "oks_before": ex.facts["oks_before"], "kl": ex.facts["kl"], "physio_weeks": ex.facts["physio_weeks"],
             "bmi": ex.facts["bmi"], "weeks_waiting": weeks, "night_pain": ex.facts["night_pain"],
             "lives_alone_or_carer": ex.facts["lives_alone_or_carer"]}
        a, b = decide(f), decide(f)
        ok3 &= check(a == b and a["pathway"] == want, f"{k['letter_id']}: decide() twice gives the same result ({a['pathway']}, rule {a['rule']})")
        examples.append([k["letter_id"], f"OKS {f['oks']}, KL {f['kl']}, physio {f['physio_weeks']} wk, BMI {f['bmi']}",
                         PATHWAYS[a["pathway"]], a["rule"], "; ".join(a["reasons"])])
    md += [""] + table(["Letter", "Facts read", "Pathway", "Rule", "Why"], examples) + [""]
    verdicts.append(("Rules decide", ok3, "schema has no pathway/priority; LLM called once; 3 examples (surgery rule 4, physio rule 3, needs info rule 1) identical on rerun"))

    # ------------------------------------------------------------------ 4. clinician decides
    md += ["## 4. The clinician decides (through the API)", "",
           "Code: " + where("backend/main.py", r'@app.post\("/patients/\{pid\}/override"\)') + "; "
           + where("backend/services.py", r"^def record_decision") + "; " + where("backend/services.py", r"^def effective_pathway"), ""]
    week0 = c.post("/week/build").json()
    physio_in = [p["id"] for p in next(l for l in week0["lists"] if l["kind"] == "physio")["in"]]
    target = next(pid for pid in physio_in if c.get(f"/patients/{pid}").json()["letter_id"])        # in this week's physio slots, with a letter
    before_override = c.get(f"/patients/{target}").json()["pathway"]
    confirmed = c.post("/patients/KP00678/confirm", json={"by": "Dr Audit", "reason": "Agree with rules"}).json()
    overridden = c.post(f"/patients/{target}/override", json={"pathway": "non_surgical", "by": "Dr Audit",
                                                               "reason": "Patient declines physio for now"}).json()
    with Session(get_engine()) as s:
        rows = s.exec(select(Decision).order_by(Decision.id)).all()
    md += table(["id", "patient", "kind", "by", "at (UTC)", "rules said", "old", "new", "reason"],
                [[d.id, d.patient_id, d.kind, d.by, d.at.isoformat(timespec="seconds"), d.rules_pathway, d.old_pathway, d.new_pathway, d.reason]
                 for d in rows]) + [""]
    ok4 = check(len(rows) == 2 and rows[0].kind == "confirmed" and rows[1].kind == "overridden", "two Decision rows: one confirm, one override")
    ok4 &= check(rows[1].old_pathway == before_override and rows[1].new_pathway == "non_surgical" and bool(rows[1].reason)
                 and rows[1].by == "Dr Audit" and rows[1].at is not None,
                 f"override stored with who (Dr Audit), when, old → new ({rows[1].old_pathway} → {rows[1].new_pathway}) and reason")
    in_physio_queue = any(r["id"] == target for r in c.get("/queue", params={"pathway": "physio"}).json())
    in_nonsurg_queue = any(r["id"] == target for r in c.get("/queue", params={"pathway": "non_surgical"}).json())
    ok4 &= check(not in_physio_queue and in_nonsurg_queue, f"queue: {target} moved from the Physio filter to Non-surgical")
    week1 = c.post("/week/build").json()
    before = {l["kind"]: [p["id"] for p in l["in"]] for l in week0["lists"]}
    after = {l["kind"]: [p["id"] for p in l["in"]] for l in week1["lists"]}
    anywhere = {pid for ids in after.values() for pid in ids}
    ok4 &= check(target not in anywhere and all(len(after[k]) == len(before[k]) for k in before),
                 f"week plan: {target} has no slot after the override, and every list is still full")
    md += [f"  - {k}: out {sorted(set(before[k]) - set(after[k])) or '—'}, in {sorted(set(after[k]) - set(before[k])) or '—'} "
           f"({len(before[k])} → {len(after[k])} slots)" for k in before]
    md.append("  - weight-support patients can use physio slots, so freeing one slot can move more than one name")
    verdicts.append(("Clinician decides", ok4, f"confirm + override stored with who, when, old/new and reason; the override moved {target} "
                     "out of the Physio queue filter and out of this week's slots, all lists still full"))

    # ------------------------------------------------------------------ 5. optimiser
    md += ["## 5. The optimiser", "",
           "Code: " + where("kneedss/optimise.py", r"^def optimise") + "; " + where("kneedss/optimise.py", r"hard and long\[pid\]")
           + "; " + where("kneedss/optimise.py", r'status = "infeasible"') + "; " + where("kneedss/optimise.py", r"^def skipped_long_waiters")
           + "; solver " + where("kneedss/optimise.py", r"^def solver\(") + "; stored plans " + where("backend/services.py", r"^def save_week"), ""]
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_optimise.py"], cwd=ROOT, capture_output=True, text=True)
    last = tests.stdout.strip().splitlines()[-1]
    ok5 = check(tests.returncode == 0, f"`pytest tests/test_optimise.py`: {last}")
    ok5 &= check(O.solver_name() == "HiGHS", f"solver: {O.solver_name()} (highspy), zero optimality gap")
    built_a, built_b = c.post("/week/build", json={"by": "Audit"}).json(), c.post("/week/build", json={"by": "Audit"}).json()
    plain = lambda w: {k: v for k, v in w.items() if k not in ("built_by", "built_at")}
    a, b = plain(built_a), plain(built_b)
    ok5 &= check(a == b, "built twice: the two plans are identical (every list, every patient, every reason)")
    ok5 &= check(c.get("/week/latest").json() == built_b and built_b["built_by"] == "Audit",
                 "each build is stored (who, when) and GET /week/latest serves the last one, so a refresh keeps it")
    for l in a["lists"]:
        ok5 &= check(len(l["in"]) <= l["capacity"], f"{l['label']}: {len(l['in'])} of {l['capacity']} slots")
    # who is waiting, from the database, with overrides applied
    with Session(get_engine()) as s:
        decisions = {d.patient_id: d for d in s.exec(select(Decision).order_by(Decision.id)).all()}
        import pandas as pd
        df = pd.DataFrame([{"patient_id": p.id, "pathway": decisions[p.id].new_pathway if p.id in decisions else p.pathway,
                            "priority_score": p.priority, "weeks_waiting": p.weeks_waiting} for p in s.exec(select(Patient)).all()])
    plan = O.optimise(df)
    assigned_ids = {p["id"] for l in a["lists"] for p in l["in"]}
    ok5 &= check(assigned_ids == set(plan.assigned.patient_id), "the API's plan and a direct optimise() on the same data give the same patients")
    if shutil.which("cbc"):
        real_solver = O.solver_name
        O.solver_name = lambda: "CBC"
        try:
            cbc_plan = O.optimise(df)
        finally:
            O.solver_name = real_solver
        same = all(sorted(plan.assigned.patient_id[plan.assigned.slot == k]) == sorted(cbc_plan.assigned.patient_id[cbc_plan.assigned.slot == k])
                   for k in O.CAPACITY)
        ok5 &= check(same, "HiGHS and CBC give the same patients in every slot on this waiting list")
    skipped = O.skipped_long_waiters(df, plan.assigned)
    ok5 &= check(skipped == [], "no patient over 52 weeks was passed over for someone under 52 weeks (skipped_long_waiters = [])")
    unmet = plan.long_wait["unmet"]
    surgery_long = int(((df.pathway == "surgery") & (df.weeks_waiting > 52)).sum())
    ok5 &= check(plan.status == "infeasible" and a["status"] == "infeasible" and a["long_wait"]["unmet"] == len(unmet) > 0,
                 f"more over-52s than slots ({surgery_long} need surgery, {a['lists'][0]['capacity']} surgery slots): "
                 f"status 'infeasible', shortfall {a['shortfall']}")
    surg = next(l for l in a["lists"] if l["kind"] == "surgery")
    ok5 &= check(all(p["long_wait"] for p in surg["in"]), "every surgery slot this week went to someone over 52 weeks")
    ok5 &= check(all(p["long_wait"] and "no slot left" in p["reason"] for p in surg["next"]),
                 f"the next in line are over-52s marked 'Over 52 weeks · no slot left' ({', '.join(p['id'] for p in surg['next'])})")
    md.append(f"- the optimiser lists all {len(unmet)} over-52s without a slot by ID (Plan.long_wait['unmet']): {', '.join(unmet[:12])}, …")
    api_unmet = [p["id"] for p in a["unmet"]]
    ok5 &= check(sorted(api_unmet) == sorted(unmet) and [p["weeks_waiting"] for p in a["unmet"]] == sorted((p["weeks_waiting"] for p in a["unmet"]), reverse=True),
                 f"the API returns all {len(api_unmet)} by name, longest wait first (This week: '{len(api_unmet)} over 52 weeks still waiting')")
    # a solver failure is reported as one, never as "all booked", with the reason only in the server log
    real_optimise = S.O.optimise
    def broken(*args, **kw):
        raise O.SolverError("audit: simulated solver failure")
    S.O.optimise = broken
    try:
        r = c.post("/week/build", json={"by": "Audit"})
    finally:
        S.O.optimise = real_optimise
    ok5 &= check(r.status_code == 500 and r.json() == {"detail": "Couldn't build the list · solver error"},
                 "a solver failure gives 500 \"Couldn't build the list · solver error\" (not 'No slot left'); the reason is logged")
    md.append("")
    verdicts.append(("Optimiser", ok5, f"{last}; HiGHS; same plan twice; plan stored and served after refresh; all slots within capacity; "
                     f"0 over-52s passed over; infeasible week reported with {len(unmet)} over-52s listed; solver errors reported as such"))

# ------------------------------------------------------------------ full suite and summary
suite = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
suite_line = suite.stdout.strip().splitlines()[-1]
commit = run(["git", "rev-parse", "--short", "HEAD"])
header = [
    "# Joint Desk audit", "",
    f"Run {datetime.now().strftime('%d/%m/%Y %H:%M')} on commit `{commit}` with `python scripts/audit.py`: a throwaway database, "
    "DEMO_MODE=1, no API calls, no behaviour changed. ✓ = check passed.", "",
    "| # | Claim | Result | Evidence |", "|---|---|---|---|",
    *[f"| {i} | {name} | **{'PASS' if ok else 'FAIL'}** | {ev} |" for i, (name, ok, ev) in enumerate(verdicts, 1)], "",
    f"Full test suite (`pytest`): **{suite_line}**", "",
]
(ROOT / "docs" / "audit.md").write_text("\n".join(header + md) + "\n")
print("\n".join(header))
if not all(ok for _, ok, _ in verdicts) or suite.returncode != 0:
    sys.exit(1)
