"""The demo site re-plans the week in the browser (frontend/src/planner.ts). It must give the optimiser's plan:
same patients in the same slots, same next in line, same reasons, same over-52 list, same changes."""
import json
import random
import shutil
import subprocess

import pandas as pd
import pytest

from backend.db import ROOT
from kneedss import optimise as O

DEMO = ROOT / "frontend" / "public" / "demo"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def browser_plan(rows: list[dict], changes: dict) -> dict:
    payload = {"patients": rows, "changes": changes, "capacity": O.CAPACITY, "long_wait": O.LONG_WAIT, "week_of": "2026-10-26"}
    out = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", str(ROOT / "tests" / "run_planner.mts")],
                         input=json.dumps(payload), capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


def optimiser_plan(rows: list[dict], changes: dict) -> dict:
    df = pd.DataFrame(rows).rename(columns={"id": "patient_id", "priority": "priority_score"})
    locked = {pid for pid, c in changes.items() if c["booked"]}
    plan = O.optimise(df, locked=locked)
    return O.plan_to_json(plan, df, dict(zip(df.patient_id, df.name)), set(df.patient_id[df.has_page]), "2026-10-26", changes)


def waiting_list() -> list[dict]:
    d = json.loads((DEMO / "waiting_list.json").read_text())
    return [dict(zip(d["columns"], r)) for r in d["rows"]]


def scenario(seed: int) -> tuple[list[dict], dict]:
    """Some overrides (into and out of slot pathways) and some bookings, from the demo waiting list."""
    rng = random.Random(seed)
    rows = waiting_list()
    changes = {}
    for r in rng.sample(rows, 15):
        new = rng.choice(["surgery", "physio", "weight_physio", "non_surgical", "review"])
        if new != r["pathway"]:
            changes[r["id"]] = {"overridden": True, "booked": False, "was": r["pathway"], "by": "Dr Test",
                                "at": f"2026-10-22T09:{len(changes):02d}:00", "reason": "test"}
            r["pathway"] = new
    slot_pathways = [r for r in rows if r["pathway"] in O.ALLOWED and r["weeks_waiting"] <= O.LONG_WAIT]
    for r in rng.sample(slot_pathways, 4):
        c = changes.setdefault(r["id"], {"overridden": False, "was": None, "reason": None})
        c.update(booked=True, by="Dr Test", at="2026-10-22T10:00:00", booking_reason="urgent")
    return rows, changes


def comparable(plan: dict) -> dict:
    out = {k: plan[k] for k in ("status", "shortfall", "patients", "long_wait", "unmet", "locked", "pushed_out", "lists")}
    out["changes"] = sorted(plan["changes"], key=lambda c: c["id"])
    return json.loads(json.dumps(out))


def test_no_changes_gives_the_exported_week():
    plan = browser_plan(waiting_list(), {})
    week = json.loads((DEMO / "week.json").read_text())
    assert plan["method"] == "demo"
    assert comparable({**plan, "changes": []}) == comparable({**week, "changes": []})


@pytest.mark.parametrize("seed", range(6))
def test_browser_plan_matches_the_optimiser_with_overrides_and_bookings(seed):
    rows, changes = scenario(seed)
    assert comparable(browser_plan(rows, changes)) == comparable(optimiser_plan(rows, changes))


def test_booking_that_pushes_out_an_over_52_names_them_in_both():
    rows = waiting_list()
    surgery = sorted((r for r in rows if r["pathway"] == "surgery" and r["weeks_waiting"] <= O.LONG_WAIT), key=lambda r: r["priority"])
    changes = {r["id"]: {"overridden": False, "booked": True, "was": None, "by": "Dr Test", "at": "2026-10-22T10:00:00",
                         "reason": None, "booking_reason": "urgent"} for r in surgery[:2]}
    browser, optimiser = browser_plan(rows, changes), optimiser_plan(rows, changes)
    assert len(browser["pushed_out"]) == 2 and browser["pushed_out"] == optimiser["pushed_out"]
    assert all(c["outcome"] == "in" and c["slot"] == "surgery" for c in browser["changes"])


def test_more_bookings_than_slots_is_refused():
    rows = waiting_list()
    surgery = [r for r in rows if r["pathway"] == "surgery"][: O.CAPACITY["surgery"] + 1]
    changes = {r["id"]: {"overridden": False, "booked": True, "was": None, "at": "2026-10-22T10:00:00"} for r in surgery}
    assert browser_plan(rows, changes) == {"error": "No slot left · all booked"}
    with pytest.raises(O.BookingsExceedCapacity):
        optimiser_plan(rows, changes)
