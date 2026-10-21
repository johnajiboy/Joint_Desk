"""Weekly slot allocation with PuLP and the CBC solver.

Each patient on the cleaned waiting list gets at most one slot this week, and only a slot type their pathway
allows: surgery -> surgery; physio -> physio; weight support and physio first -> weight support, or physio if the
weight support slots are full. Everyone over 52 weeks with a matching slot type must get a slot. If they can't all
fit, the plan says so (status "infeasible") and lists them by name; it then fills the slots with as many of them
as fit, rather than quietly skipping anyone. Within that, the objective is the total priority score, with a
bonus for weeks waiting that is too small to beat one priority point, so it only breaks ties.

Needs the `cbc` binary (`brew install cbc`); set CBC_PATH to use another one.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass, field

import pandas as pd
import pulp

SLOT_NAMES = {"surgery": "Surgery", "physio": "Physio", "weight_support": "Weight support"}
CAPACITY = {"surgery": 12, "physio": 20, "weight_support": 8}
LONG_WAIT = 52            # weeks: the NHS maximum wait; over this a patient must get a slot
STANDARD_WEEKS = 18       # weeks: the NHS referral-to-treatment target
# Slot types each pathway may use, preferred first.
ALLOWED = {"surgery": ["surgery"], "physio": ["physio"], "weight_physio": ["weight_support", "physio"]}
NEXT_SHOWN = 5


def cbc_path() -> str | None:
    """CBC_PATH, else `cbc` on PATH (brew install cbc), else the binary in the cbcbox package (Linux servers)."""
    path = os.environ.get("CBC_PATH") or shutil.which("cbc")
    if path:
        return path
    spec = importlib.util.find_spec("cbcbox")
    if spec and spec.origin:
        candidate = os.path.join(os.path.dirname(spec.origin), "cbc_dist", "bin", "cbc")
        if os.access(candidate, os.X_OK):
            return candidate
    return None


def solver() -> pulp.LpSolver:
    path = cbc_path()
    if not path:
        raise RuntimeError("CBC not found: install it with `brew install cbc` or set CBC_PATH")
    return pulp.getSolver("COIN_CMD", path=path, msg=False)


@dataclass
class Plan:
    status: str                                   # "optimal" or "infeasible" (over-52s didn't all fit)
    assigned: pd.DataFrame                        # patient_id, slot, priority, weeks_waiting, long_wait, reason
    next: dict[str, pd.DataFrame]                 # per slot type: the next patients in line, with the reason
    capacity: dict[str, int]
    slots_used: dict[str, int]
    long_wait: dict                               # weeks, total, included, unmet (patient ids)
    shortfall: list[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return self.status == "optimal"


def _weights(cand: pd.DataFrame, capacity: dict[str, int]) -> tuple[float, float]:
    """Tie-break sizes. Over all chosen patients, weeks bonuses add up to less than one priority point, and
    slot-preference bonuses to less than one week."""
    slots = sum(capacity.values()) + 1
    eps = 1 / (slots * (float(cand.weeks_waiting.max()) + 1) + 1)
    return eps, eps / (slots + 1)


def shortfall(cand: pd.DataFrame, capacity: dict[str, int], long_wait: int = LONG_WAIT) -> list[str]:
    """Plain-language reasons the over-52 patients can't all have a slot."""
    long = cand[cand.weeks_waiting > long_wait].pathway.value_counts()
    out = []
    s, p, w = long.get("surgery", 0), long.get("physio", 0), long.get("weight_physio", 0)
    if s > capacity["surgery"]:
        out.append(f"{s} over {long_wait} weeks need surgery; {capacity['surgery']} slots")
    if p > capacity["physio"]:
        out.append(f"{p} over {long_wait} weeks need physio; {capacity['physio']} slots")
    if w > capacity["weight_support"] + max(0, capacity["physio"] - p):
        out.append(f"{w} over {long_wait} weeks need weight support; "
                   f"{capacity['weight_support']} slots + {max(0, capacity['physio'] - p)} spare physio")
    return out


def optimise(df: pd.DataFrame, capacity: dict[str, int] | None = None, long_wait: int = LONG_WAIT,
             fallback: bool = True) -> Plan:
    """Plan one week. `df` needs patient_id, pathway, priority_score and weeks_waiting.

    With fallback=False an infeasible week returns no assignments, just the shortfall."""
    capacity = {**CAPACITY, **(capacity or {})}
    cand = df[df.pathway.isin(ALLOWED)].set_index("patient_id", drop=False)
    long = cand.weeks_waiting > long_wait
    eps, eps2 = _weights(cand, capacity) if len(cand) else (0.0, 0.0)
    pairs = [(pid, s) for pid, pw in cand.pathway.items() for s in ALLOWED[pw] if capacity.get(s, 0) > 0]

    def score(pid: str, s: str) -> float:
        r = cand.loc[pid]
        return float(r.priority_score) + eps * float(r.weeks_waiting) + (eps2 if s == ALLOWED[r.pathway][0] else 0)

    def build(hard: bool) -> tuple[pulp.LpProblem, dict]:
        prob = pulp.LpProblem("week", pulp.LpMaximize)
        x = {(pid, s): prob.add_variable(f"x_{pid}_{s}", lowBound=0, upBound=1, cat="Binary") for pid, s in pairs}
        by_patient: dict[str, list] = {}
        by_slot: dict[str, list] = {s: [] for s in capacity}
        for (pid, s), v in x.items():
            by_patient.setdefault(pid, []).append(v)
            by_slot[s].append(v)
        # lexicographic fallback: first as many over-52s as fit, then priority (big > any total of scores)
        big = 0 if hard else 1000 * (sum(capacity.values()) + 1)
        prob += pulp.lpSum([(score(pid, s) + (big if long[pid] else 0)) * v for (pid, s), v in x.items()])
        for pid, vs in by_patient.items():
            prob += (pulp.lpSum(vs) == 1) if (hard and long[pid]) else (pulp.lpSum(vs) <= 1)
        for s, vs in by_slot.items():
            if vs:
                prob += pulp.lpSum(vs) <= capacity[s]
        return prob, x

    status = "optimal"
    prob, x = build(hard=True)
    stats = prob.solve(solver())
    if stats.status != pulp.LpSolveStatus.Optimal:
        status = "infeasible"
        if not fallback:
            return Plan(status, pd.DataFrame(columns=["patient_id", "slot"]), {}, capacity,
                        {s: 0 for s in capacity}, {"weeks": long_wait, "total": int(long.sum()), "included": 0,
                                                    "unmet": list(cand.index[long])}, shortfall(cand, capacity, long_wait))
        prob, x = build(hard=False)
        stats = prob.solve(solver())
        if stats.status != pulp.LpSolveStatus.Optimal:
            raise RuntimeError(f"CBC could not solve the fallback plan: {stats.status}")

    chosen = [(pid, s) for (pid, s), v in x.items() if (v.value() or 0) > 0.5]
    assigned = cand.loc[[pid for pid, _ in chosen], ["patient_id", "pathway", "priority_score", "weeks_waiting"]].copy()
    assigned["slot"] = [s for _, s in chosen]
    assigned["long_wait"] = assigned.weeks_waiting > long_wait
    assigned = assigned.sort_values(["slot", "long_wait", "priority_score", "weeks_waiting"],
                                    ascending=[True, False, False, False]).reset_index(drop=True)

    # cut-off: the lowest priority that won a slot on merit (not by the over-52 rule), per slot type
    merit = assigned[~assigned.long_wait]
    cut = merit.groupby("slot").priority_score.min().to_dict()

    def reason_in(r) -> str:
        if r.long_wait:
            return f"Over {long_wait} weeks ({r.weeks_waiting}) · must have a slot"
        moved = r.pathway == "weight_physio" and r.slot == "physio"
        return f"Priority {r.priority_score} · {r.weeks_waiting} weeks" + (" · physio slot, weight support full" if moved else "")
    assigned["reason"] = [reason_in(r) for r in assigned.itertuples()]

    waiting = cand[~cand.patient_id.isin(assigned.patient_id)].copy()
    waiting["long_wait"] = waiting.weeks_waiting > long_wait
    nxt = {}
    for s in capacity:
        pool = waiting[waiting.pathway.isin([p for p, allowed in ALLOWED.items() if s in allowed])]
        pool = pool.sort_values(["long_wait", "priority_score", "weeks_waiting"], ascending=False).head(NEXT_SHOWN).copy()
        pool["reason"] = [
            f"Over {long_wait} weeks · no slot left" if r.long_wait
            else f"Priority {r.priority_score} · below the cut-off ({cut[s]})" if s in cut
            else f"Priority {r.priority_score} · slots full"
            for r in pool.itertuples()]
        nxt[s] = pool[["patient_id", "pathway", "priority_score", "weeks_waiting", "long_wait", "reason"]].reset_index(drop=True)

    unmet = sorted(waiting.patient_id[waiting.long_wait])
    return Plan(
        status=status, assigned=assigned, next=nxt, capacity=capacity,
        slots_used={s: int((assigned.slot == s).sum()) for s in capacity},
        long_wait={"weeks": long_wait, "total": int(long.sum()), "included": int(assigned.long_wait.sum()), "unmet": unmet},
        shortfall=shortfall(cand, capacity, long_wait) if status == "infeasible" else [],
    )


def skipped_long_waiters(df: pd.DataFrame, assigned: pd.DataFrame, long_wait: int = LONG_WAIT) -> list[str]:
    """Over-52 patients left without a slot while a slot they could use went to someone who isn't over 52.
    The optimiser's hard rule means this is always empty for its plans."""
    cand = df[df.pathway.isin(list(ALLOWED))]
    a = assigned.merge(cand[["patient_id", "weeks_waiting"]], on="patient_id", how="left", suffixes=("", "_c"))
    given_to_short = set(a.slot[a.weeks_waiting <= long_wait])
    left = cand[(cand.weeks_waiting > long_wait) & ~cand.patient_id.isin(assigned.patient_id)]
    return sorted(left.patient_id[left.pathway.map(lambda p: bool(set(ALLOWED[p]) & given_to_short))])


def plan_to_json(plan: Plan, patients: pd.DataFrame, names: dict[str, str], with_page: set[str], week_of: str) -> dict:
    """The plan as the This week page reads it (week.json and the backend's POST /week/build)."""
    eligible = patients[patients.pathway.isin(list(ALLOWED))]

    def person(r) -> dict:
        return {"id": r.patient_id, "name": names.get(r.patient_id, r.patient_id), "pathway": r.pathway,
                "priority": int(r.priority_score), "weeks_waiting": int(r.weeks_waiting), "long_wait": bool(r.long_wait),
                "reason": r.reason, "has_page": r.patient_id in with_page}

    lists = []
    for slot, label in SLOT_NAMES.items():
        chosen = plan.assigned[plan.assigned.slot == slot]
        can_use = eligible.pathway.isin([p for p, allowed in ALLOWED.items() if slot in allowed])
        lists.append({"kind": slot, "label": label, "capacity": plan.capacity[slot],
                      "in": [person(r) for r in chosen.itertuples()],
                      "next": [person(r) for r in plan.next[slot].itertuples()],
                      "waiting": int(can_use.sum()) - len(chosen)})
    return {"week_of": week_of, "method": "optimiser", "status": plan.status, "shortfall": plan.shortfall,
            "patients": len(eligible), "lists": lists,
            "long_wait": {k: (len(v) if k == "unmet" else v) for k, v in plan.long_wait.items()}}
