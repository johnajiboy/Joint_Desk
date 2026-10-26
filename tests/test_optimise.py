import importlib.util
import shutil
from pathlib import Path

import pandas as pd
import pulp
import pytest

from kneedss import optimise as O

pytestmark = pytest.mark.skipif(not (importlib.util.find_spec("highspy") or shutil.which("cbc")),
                                reason="needs a solver (pip install highspy)")

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


def test_surgery_list_series_one_seed_and_mean():
    lists = pd.DataFrame([{"seed": s, "triage": t, "week": w, "surgery_list": base + s * 10 + w}
                          for s in (1, 2) for t, base in (("on", 100), ("off", 200)) for w in (0, 1, 2)])
    out = E.surgery_list_series(lists, 1)
    assert out["weeks"] == [0, 1, 2] and out["seeds"] == 2
    assert out["on"] == [110, 111, 112] and out["off"] == [210, 211, 212]
    assert out["mean_on"] == [115, 116, 117] and out["mean_off"] == [215, 216, 217]


def test_backlog_counts_add_up():
    from kneedss.results import backlog_results
    b = backlog_results()
    assert sum(b["by_pathway"].values()) == b["patients"] == 1500
    assert b["surgery"] == b["by_pathway"]["surgery"]
    assert b["over_long_wait"] <= b["over_standard"] <= b["waiting_for_slot"]
    assert (b["standard_weeks"], b["long_wait_weeks"]) == (O.STANDARD_WEEKS, O.LONG_WAIT)


def test_plan_json_lists_every_unmet_over_52_longest_wait_first():
    w = pd.read_csv(ROOT / "data" / "output" / "waiting_list.csv")
    plan = O.optimise(w)
    out = O.plan_to_json(plan, w, dict(zip(w.patient_id, w.first_name + " " + w.surname)), set(), "2026-10-26")
    assert len(out["unmet"]) == out["long_wait"]["unmet"] == len(plan.long_wait["unmet"]) > 0
    assert {p["id"] for p in out["unmet"]} == set(plan.long_wait["unmet"])
    weeks = [p["weeks_waiting"] for p in out["unmet"]]
    assert weeks == sorted(weeks, reverse=True) and min(weeks) > O.LONG_WAIT
    assert set(out["unmet"][0]) >= {"id", "name", "weeks_waiting", "priority", "has_page"}


def _week(rows):
    return pd.DataFrame(rows, columns=["patient_id", "pathway", "priority_score", "weeks_waiting"])


def test_locked_patient_is_always_in_and_counts_against_capacity():
    df = _week([("A", "surgery", 90, 10), ("B", "surgery", 80, 10), ("L", "surgery", 5, 2)])
    plan = O.optimise(df, capacity={"surgery": 2})
    assert "L" not in set(plan.assigned.patient_id)
    plan = O.optimise(df, capacity={"surgery": 2}, locked={"L"})
    assert set(plan.assigned.patient_id) == {"A", "L"}
    assert plan.pushed_out == []


def test_overridden_patient_moves_into_the_right_list():
    df = _week([("A", "physio", 70, 10), ("B", "surgery", 60, 10)])
    plan = O.optimise(df.assign(pathway=["surgery", "surgery"]), capacity={"surgery": 2})
    assert set(plan.assigned.patient_id[plan.assigned.slot == "surgery"]) == {"A", "B"}


def test_lock_never_silently_pushes_out_an_over_52():
    df = _week([("O", "surgery", 10, 60), ("L", "surgery", 5, 2)])
    plan = O.optimise(df, capacity={"surgery": 1}, locked={"L"})
    assert set(plan.assigned.patient_id) == {"L"}
    assert plan.status == "infeasible" and plan.pushed_out == ["O"]


# ---------------------------------------------------------------- solver

def test_highs_is_the_default_and_cbc_only_a_fallback(monkeypatch):
    assert O.solver_name() == "HiGHS"
    real = importlib.util.find_spec
    monkeypatch.setattr(O.importlib.util, "find_spec", lambda name: None if name == "highspy" else real(name))
    monkeypatch.setattr(O, "cbc_path", lambda: "/usr/local/bin/cbc")
    assert O.solver_name() == "CBC"
    monkeypatch.setattr(O, "cbc_path", lambda: None)
    with pytest.raises(O.SolverError, match="pip install highspy"):
        O.solver_name()


@pytest.mark.skipif(not (shutil.which("cbc") and importlib.util.find_spec("highspy")), reason="needs both solvers")
@pytest.mark.parametrize("capacity", [None, {"surgery": 8}, {"surgery": 16}])
def test_highs_gives_the_cbc_plan_on_the_real_waiting_list(monkeypatch, capacity):
    wl = pd.read_csv(Path(__file__).resolve().parent.parent / "data" / "output" / "waiting_list.csv")
    highs = O.optimise(wl, capacity=capacity)
    monkeypatch.setattr(O, "solver_name", lambda: "CBC")
    cbc = O.optimise(wl, capacity=capacity)
    assert highs.status == cbc.status
    for slot in O.CAPACITY:
        assert sorted(highs.assigned.patient_id[highs.assigned.slot == slot]) == sorted(cbc.assigned.patient_id[cbc.assigned.slot == slot])
        assert list(highs.next[slot].patient_id) == list(cbc.next[slot].patient_id)


def test_only_real_overbooking_is_bookings_exceed_capacity():
    df = _week([(f"S{i}", "surgery", 50, 10) for i in range(3)] + [("W1", "weight_physio", 40, 5), ("P1", "physio", 30, 5)])
    with pytest.raises(O.BookingsExceedCapacity):
        O.optimise(df, capacity={"surgery": 2}, locked={"S0", "S1", "S2"})
    # weight support bookings may spill into physio slots the physio bookings leave
    plan = O.optimise(df, capacity={"weight_support": 0, "physio": 2}, locked={"W1", "P1"})
    assert set(plan.assigned.patient_id[plan.assigned.slot == "physio"]) == {"W1", "P1"}
    with pytest.raises(O.BookingsExceedCapacity):
        O.optimise(df, capacity={"weight_support": 0, "physio": 1}, locked={"W1", "P1"})


def test_a_solver_failure_is_a_solver_error_not_an_infeasible_week(monkeypatch):
    class Broken(pulp.LpSolver):
        def actualSolve(self, lp, **kw):
            raise OSError("solver binary killed (status -7)")
    monkeypatch.setattr(O, "solver", lambda: Broken())
    with pytest.raises(O.SolverError, match="status -7"):
        O.optimise(_week([("A", "surgery", 50, 10)]))
