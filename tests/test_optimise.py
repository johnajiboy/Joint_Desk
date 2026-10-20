import importlib.util
import shutil
from pathlib import Path

import pandas as pd
import pytest

from kneedss import optimise as O

pytestmark = pytest.mark.skipif(not shutil.which("cbc"), reason="needs the cbc solver (brew install cbc)")

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eval_optimise", ROOT / "eval" / "eval_optimise.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def people(*rows):
    """(id, pathway, priority, weeks) tuples -> the columns optimise() needs."""
    return pd.DataFrame(rows, columns=["patient_id", "pathway", "priority_score", "weeks_waiting"])


def slots(plan):
    return dict(zip(plan.assigned.patient_id, plan.assigned.slot))


def test_capacity_and_eligibility():
    df = people(*[(f"S{i}", "surgery", 50 + i, 10) for i in range(5)], ("P1", "physio", 90, 10),
                ("R1", "review", 99, 60), ("N1", "non_surgical", 99, 60))
    plan = O.optimise(df, {"surgery": 3, "physio": 1, "weight_support": 1})
    got = slots(plan)
    assert plan.feasible and plan.slots_used == {"surgery": 3, "physio": 1, "weight_support": 0}
    assert set(got) == {"S4", "S3", "S2", "P1"} and got["P1"] == "physio"
    assert "R1" not in got and "N1" not in got                     # no slot type for these pathways
    assert plan.assigned.patient_id.is_unique


def test_weight_support_patients_use_physio_when_their_slots_are_full():
    df = people(("W1", "weight_physio", 80, 5), ("W2", "weight_physio", 70, 5), ("P1", "physio", 10, 5))
    got = slots(O.optimise(df, {"surgery": 0, "physio": 1, "weight_support": 1}))
    # both weight-support patients beat the lower-priority physio patient; which takes which slot is a tie
    assert set(got) == {"W1", "W2"} and sorted(got.values()) == ["physio", "weight_support"]
    got = slots(O.optimise(df, {"surgery": 0, "physio": 2, "weight_support": 2}))
    assert got["W1"] == got["W2"] == "weight_support" and got["P1"] == "physio"


def test_ties_go_to_the_longest_waiter_but_never_beat_priority():
    df = people(("A", "surgery", 60, 10), ("B", "surgery", 60, 40), ("C", "surgery", 61, 1))
    assert set(slots(O.optimise(df, {"surgery": 1, "physio": 0, "weight_support": 0}))) == {"C"}
    assert set(slots(O.optimise(df, {"surgery": 2, "physio": 0, "weight_support": 0}))) == {"C", "B"}


def test_over_52_must_have_a_slot_even_with_low_priority():
    df = people(("HIGH", "surgery", 95, 10), ("LONG", "surgery", 20, 60))
    plan = O.optimise(df, {"surgery": 1, "physio": 0, "weight_support": 0})
    assert plan.feasible and set(slots(plan)) == {"LONG"}
    assert plan.assigned.reason[0].startswith("Over 52 weeks")
    assert plan.next["surgery"].patient_id.tolist() == ["HIGH"] and "cut-off" not in plan.next["surgery"].reason[0]


def test_too_many_over_52s_is_reported_infeasible_not_skipped():
    df = people(*[(f"L{i}", "surgery", 30 + i, 53 + i) for i in range(4)], ("HIGH", "surgery", 99, 5))
    cap = {"surgery": 2, "physio": 0, "weight_support": 0}
    plan = O.optimise(df, cap)
    assert plan.status == "infeasible" and plan.shortfall == ["4 over 52 weeks need surgery; 2 slots"]
    assert set(slots(plan)) == {"L3", "L2"}                         # every slot goes to an over-52
    assert plan.long_wait["unmet"] == ["L0", "L1"] and "HIGH" not in slots(plan)
    assert O.skipped_long_waiters(df, plan.assigned) == []
    strict = O.optimise(df, cap, fallback=False)
    assert strict.status == "infeasible" and strict.assigned.empty and len(strict.long_wait["unmet"]) == 4


def test_skip_detection():
    df = people(("HIGH", "surgery", 95, 10), ("LONG", "surgery", 20, 60))
    assert O.skipped_long_waiters(df, pd.DataFrame({"patient_id": ["HIGH"], "slot": ["surgery"]})) == ["LONG"]
    assert O.skipped_long_waiters(df, pd.DataFrame({"patient_id": ["LONG"], "slot": ["surgery"]})) == []


def test_real_waiting_list_plan():
    w = pd.read_csv(ROOT / "data" / "output" / "waiting_list.csv")
    plan = O.optimise(w)
    assert plan.status == "infeasible" and plan.slots_used == O.CAPACITY
    surgery = plan.assigned[plan.assigned.slot == "surgery"]
    assert surgery.long_wait.all()                                  # 57 over-52s need surgery, 12 slots
    assert len(plan.long_wait["unmet"]) == plan.long_wait["total"] - plan.long_wait["included"]
    assert O.skipped_long_waiters(w, plan.assigned) == []
    assert plan.assigned.reason.str.len().gt(0).all()


@pytest.fixture(scope="module")
def sim():
    start = pd.read_csv(ROOT / "data" / "output" / "waiting_list.csv")
    start["static"] = E.static_points(start)
    new = E.arrivals(start, E.arrival_rate(start), 8, E.SEED)
    return start, new


@pytest.mark.parametrize("cap", [8, 12, 16])
def test_no_over_52_patient_is_ever_skipped_by_the_optimiser(sim, cap):
    start, new = sim
    capacity = {**O.CAPACITY, "surgery": cap}
    weekly, served, skipped = E.simulate(start, new, "Optimiser", capacity)
    assert skipped == set() and weekly.skipped_over_52.sum() == 0
    assert served.patient_id.is_unique                              # nobody treated twice
    per_week = served.groupby(["week", "slot"]).size()
    assert all(per_week[(w, s)] <= capacity[s] for w, s in per_week.index)


def test_priority_only_does_skip_over_52s(sim):
    start, new = sim
    _, _, skipped = E.simulate(start, new, "Priority only", O.CAPACITY)
    assert len(skipped) > 0


def test_priority_tracks_rules_priority_score():
    from kneedss.rules import priority_score
    w = pd.read_csv(ROOT / "data" / "output" / "waiting_list.csv").head(50)
    static = E.static_points(w)
    got = E.priority(static, w.weeks_waiting + 10)
    want = [priority_score({"oks": None if pd.isna(r.oks) else r.oks, "oks_before": r.oks_before,
                            "kl": None if pd.isna(r.kl_grade) else r.kl_grade, "weeks_waiting": r.weeks_waiting + 10,
                            "night_pain": r.night_pain, "lives_alone_or_carer": r.lives_alone_or_carer})
            for r in w.itertuples()]
    assert got.tolist() == want


def test_everyone_fits():
    df = people(("A", "surgery", 60, 10), ("B", "physio", 50, 60))
    plan = O.optimise(df)
    assert plan.feasible and set(slots(plan)) == {"A", "B"}
    assert all(n.empty for n in plan.next.values()) and plan.long_wait["unmet"] == []


def test_triage_off_puts_every_kl2_plus_on_the_surgery_list():
    df = pd.DataFrame({"kl_grade": [1.0, 2.0, 3.0, 4.0, None],
                       "pathway": ["non_surgical", "physio", "weight_physio", "review", "review"]})
    assert E.triage_off(df).pathway.tolist() == ["non_surgical", "surgery", "surgery", "surgery", "review"]
    assert df.pathway.tolist()[1] == "physio"                       # the input is not changed


def test_ci95_uses_the_t_distribution():
    m, lo, hi = E.ci95(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert m == 2.5 and lo == pytest.approx(2.5 - 3.182446 * 1.290994 / 2, abs=1e-4) and hi - m == pytest.approx(m - lo)
    assert E.ci95(pd.Series([5.0, 5.0, 5.0])) == (5.0, 5.0, 5.0)


def test_robustness_verdicts():
    rows = []
    for seed in range(5):
        for policy, skipped, wait in [("FCFS", 0, 50 + seed), ("Priority only", 10 + seed, 30), ("Optimiser", 0, 45 + seed % 2),
                                      (E.TRIAGE_OFF, 0, 60)]:
            rows.append({"policy": policy, "seed": seed, "surgery_list_start": 1, **{k: 0 for k in E.METRICS},
                         "over_52_skipped_patients": skipped, "mean_wait_surgery": wait})
    _, pairs = E.robustness_tables(pd.DataFrame(rows))
    v = pairs.set_index(["comparison", "metric"]).verdict
    assert v[("Optimiser - FCFS", "over_52_skipped_patients")] == "same in every seed"
    assert v[("Optimiser - Priority only", "over_52_skipped_patients")] == "holds: lower in 5/5 seeds"
    assert v[("Optimiser - Priority only", "mean_wait_surgery")] == "holds: higher in 5/5 seeds"
    assert v[("Optimiser - FCFS", "mean_wait_surgery")].startswith("holds: lower in")
