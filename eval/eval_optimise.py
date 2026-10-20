"""Simulate 26 weeks of the waiting list under three policies, then vary surgery capacity. No API calls.

Policies: first come first served (longest wait first), priority only (highest priority score first) and the
optimiser (kneedss/optimise.py: over-52s first as a hard rule, then total priority). Every policy sees the same
new referrals each week. Each week: new referrals join, each policy fills its slots, the people treated leave,
everyone else waits a week longer, and priority scores update for the extra wait.

Arrival rate: the generator draws a snapshot of waits rather than an arrival process, so the rate is the one its
referral dates imply: patients referred in the last 52 weeks / 53 weeks. New referrals are drawn from the cleaned
list (same mix of pathways and clinical values) and start at 0 weeks.

    python eval/eval_optimise.py     -> eval/results/optimise/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import optimise as O         # noqa: E402
from kneedss.rules import priority_breakdown, PRIORITY_MAX   # noqa: E402

OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results" / "optimise"
WEEKS = 26
SEED = 2026
SURGERY_CAPACITIES = [8, 12, 16]
POLICIES = ["FCFS", "Priority only", "Optimiser"]
ELIGIBLE = list(O.ALLOWED)


# ---------------------------------------------------------------------------- the list

def static_points(df: pd.DataFrame) -> pd.Series:
    """Priority points that don't change with time (everything except time waiting)."""
    def pts(r):
        f = {"oks": None if pd.isna(r.oks) else r.oks, "oks_before": r.oks_before,
             "kl": None if pd.isna(r.kl_grade) else r.kl_grade, "weeks_waiting": 0,
             "night_pain": r.night_pain, "lives_alone_or_carer": r.lives_alone_or_carer}
        b = priority_breakdown(f)
        return b["pain_function"] + b["xray"] + b["decline"] + b["social"]
    return df.apply(pts, axis=1)


def priority(static: pd.Series, weeks: pd.Series) -> pd.Series:
    """rules.priority_score with the waiting part recomputed for the current wait."""
    waiting = (np.minimum(weeks, 78) / 78 * 16).round()
    return ((static + waiting) / sum(PRIORITY_MAX.values()) * 100).round().astype(int)


def arrival_rate(df: pd.DataFrame) -> float:
    return float((df.weeks_waiting <= 52).sum() / 53)


def arrivals(df: pd.DataFrame, rate: float, weeks: int, seed: int) -> list[pd.DataFrame]:
    """Same new referrals for every policy: Poisson numbers, drawn from the cleaned list."""
    rng = np.random.default_rng(seed)
    out = []
    for w in range(weeks):
        n = int(rng.poisson(rate))
        new = df.sample(n=n, replace=True, random_state=int(rng.integers(1 << 31))).copy()
        new["patient_id"] = [f"N{w + 1:02d}-{i:03d}" for i in range(n)]
        new["weeks_waiting"] = 0
        out.append(new)
    return out


# ---------------------------------------------------------------------------- policies

def _fill(cand: pd.DataFrame, capacity: dict, order: list[str]) -> pd.DataFrame:
    """Shared greedy fill for the two simple policies: weight support first, then physio (which weight-support
    patients may also use), then surgery, each taking patients in `order`."""
    taken, rows = set(), []
    for slot in ["weight_support", "physio", "surgery"]:
        pool = cand[cand.pathway.map(lambda p: slot in O.ALLOWED[p]) & ~cand.patient_id.isin(taken)]
        pool = pool.sort_values(order, ascending=[False] * (len(order) - 1) + [True]).head(capacity[slot])
        taken |= set(pool.patient_id)
        rows.append(pd.DataFrame({"patient_id": pool.patient_id, "slot": slot}))
    return pd.concat(rows, ignore_index=True)


def fcfs(cand, capacity):
    return _fill(cand, capacity, ["weeks_waiting", "patient_id"])


def priority_only(cand, capacity):
    return _fill(cand, capacity, ["priority_score", "patient_id"])


def optimiser(cand, capacity):
    plan = O.optimise(cand, capacity)
    return plan.assigned[["patient_id", "slot"]], plan.status


# ---------------------------------------------------------------------------- simulation

def simulate(start: pd.DataFrame, new: list[pd.DataFrame], policy: str, capacity: dict) -> tuple[pd.DataFrame, pd.DataFrame, set]:
    pool = start[start.pathway.isin(ELIGIBLE)].copy()
    weekly, served, skipped = [], [], set()
    for w in range(1, len(new) + 1):
        pool = pd.concat([pool, new[w - 1][new[w - 1].pathway.isin(ELIGIBLE)]], ignore_index=True)
        pool["priority_score"] = priority(pool.static, pool.weeks_waiting)
        status = "optimal"
        if policy == "FCFS":
            chosen = fcfs(pool, capacity)
        elif policy == "Priority only":
            chosen = priority_only(pool, capacity)
        else:
            chosen, status = optimiser(pool, capacity)
        missed = O.skipped_long_waiters(pool, chosen)
        skipped |= set(missed)
        got = pool.merge(chosen, on="patient_id")
        served.append(got.assign(week=w))
        over52_before = int((pool.weeks_waiting > 52).sum())
        pool = pool[~pool.patient_id.isin(chosen.patient_id)].copy()
        weekly.append({"policy": policy, "surgery_capacity": capacity["surgery"], "week": w,
                       "waiting": len(pool), "over_18": int((pool.weeks_waiting > 18).sum()),
                       "over_52": int((pool.weeks_waiting > 52).sum()), "over_52_at_start": over52_before,
                       "served": len(got), "skipped_over_52": len(missed), "infeasible": status == "infeasible",
                       **{f"waiting_{p}": int((pool.pathway == p).sum()) for p in ELIGIBLE}})
        pool["weeks_waiting"] += 1
    return pd.DataFrame(weekly), pd.concat(served, ignore_index=True), skipped


def summarise(weekly: pd.DataFrame, served: pd.DataFrame, skipped: set, policy: str, cap: int) -> dict:
    surg = served[served.slot == "surgery"]
    return {
        "policy": policy, "surgery_capacity": cap,
        "over_18_end": int(weekly.over_18.iloc[-1]), "over_52_end": int(weekly.over_52.iloc[-1]),
        "over_52_mean": round(weekly.over_52.mean(), 1),
        "over_52_skipped_patients": len(skipped), "over_52_skipped_patient_weeks": int(weekly.skipped_over_52.sum()),
        "weeks_infeasible": int(weekly.infeasible.sum()), "served": len(served),
        **{f"mean_wait_{p}": round(served.weeks_waiting[served.pathway == p].mean(), 1) for p in ELIGIBLE},
        "mean_oks_operated": round(surg.oks.mean(), 1), "operated": len(surg),
        "waiting_end": int(weekly.waiting.iloc[-1]),
    }


def charts(weekly: pd.DataFrame, summary: pd.DataFrame) -> None:
    base = weekly[weekly.surgery_capacity == 12]
    # validated categorical slots 1-3 (dataviz reference palette); dashes keep overlapping lines visible
    styles = {"Optimiser": ("#2a78d6", "-"), "FCFS": ("#eb6834", "--"), "Priority only": ("#1baf7a", ":")}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharex=True)
    for ax, col, title in [(axes[0], "over_18", "Waiting over 18 weeks"), (axes[1], "over_52", "Waiting over 52 weeks")]:
        for p in POLICIES:
            d = base[base.policy == p]
            c, ls = styles[p]
            ax.plot(d.week, d[col], color=c, linestyle=ls, linewidth=2, label=p)
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_xlabel("Week")
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Patients (surgery, physio, weight support)")
    axes[1].legend(frameon=False)
    fig.suptitle("Backlog over 26 weeks, surgery capacity 12 a week", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(RESULTS / "backlog.png", dpi=150)
    plt.close(fig)

    s12 = summary[summary.surgery_capacity == 12].set_index("policy").loc[POLICIES]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(ELIGIBLE))
    for i, p in enumerate(POLICIES):
        ax.bar(x + (i - 1) * 0.26, [s12.loc[p, f"mean_wait_{k}"] for k in ELIGIBLE], 0.26, label=p, color=styles[p][0])
    ax.set_xticks(x, ["Surgery", "Physio", "Weight + physio"])
    ax.set_ylabel("Mean weeks waited when treated")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(RESULTS / "wait_by_pathway.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    for p in POLICIES:
        d = summary[summary.policy == p]
        axes[0].plot(d.surgery_capacity, d.over_52_end, marker="o", color=styles[p][0], linestyle=styles[p][1], label=p)
        axes[1].plot(d.surgery_capacity, d.mean_oks_operated, marker="o", color=styles[p][0], linestyle=styles[p][1], label=p)
    axes[0].set_title("Over 52 weeks after 26 weeks", loc="left", fontsize=11)
    axes[1].set_title("Mean OKS of patients operated on (lower = worse knees)", loc="left", fontsize=11)
    for ax in axes:
        ax.set_xlabel("Surgery slots a week")
        ax.set_xticks(SURGERY_CAPACITIES)
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(RESULTS / "sensitivity.png", dpi=150)
    plt.close(fig)


def fmt(t: pd.DataFrame) -> pd.DataFrame:
    """Whole numbers without decimals, the rest to one decimal place."""
    def one(v):
        if isinstance(v, (int, np.integer)) or (isinstance(v, float) and v.is_integer() and abs(v) >= 0):
            return f"{int(v):,}" if not (isinstance(v, float) and not v.is_integer()) else f"{v:.1f}"
        return f"{v:.1f}" if isinstance(v, (float, np.floating)) else v
    return t.astype(object).map(one)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    start = pd.read_csv(OUT / "waiting_list.csv")
    start["static"] = static_points(start)
    rate = arrival_rate(start)
    new = arrivals(start, rate, WEEKS, SEED)

    weekly_all, rows = [], []
    for cap in SURGERY_CAPACITIES:
        capacity = {**O.CAPACITY, "surgery": cap}
        for p in POLICIES:
            weekly, served, skipped = simulate(start, new, p, capacity)
            weekly_all.append(weekly)
            rows.append(summarise(weekly, served, skipped, p, cap))
            if cap == 12:
                served.to_csv(RESULTS / f"served_{p.lower().replace(' ', '_')}.csv", index=False)
    weekly = pd.concat(weekly_all, ignore_index=True)
    summary = pd.DataFrame(rows)
    weekly.to_csv(RESULTS / "weekly.csv", index=False)
    summary.to_csv(RESULTS / "summary.csv", index=False)
    charts(weekly, summary)

    s12 = summary[summary.surgery_capacity == 12].set_index("policy").loc[POLICIES]
    start_el = start[start.pathway.isin(ELIGIBLE)]
    table = pd.DataFrame({
        "Over 18 weeks, end": s12.over_18_end, "Over 52 weeks, end": s12.over_52_end,
        "Over 52, weekly mean": s12.over_52_mean,
        "Over-52 patients skipped": s12.over_52_skipped_patients,
        "Weeks over-52s didn't fit": s12.weeks_infeasible,
        "Mean wait, surgery": s12.mean_wait_surgery, "Mean wait, physio": s12.mean_wait_physio,
        "Mean wait, weight + physio": s12.mean_wait_weight_physio,
        "Mean OKS operated on": s12.mean_oks_operated, "Treated": s12.served,
    })
    sens = summary.assign(policy=pd.Categorical(summary.policy, POLICIES)).sort_values(["surgery_capacity", "policy"])[
        ["surgery_capacity", "policy", "over_52_end", "over_52_mean", "over_18_end", "over_52_skipped_patients",
         "weeks_infeasible", "mean_wait_surgery", "mean_oks_operated"]].rename(columns={
            "surgery_capacity": "Surgery slots", "policy": "Policy", "over_52_end": "Over 52, end",
            "over_52_mean": "Over 52, weekly mean", "over_18_end": "Over 18, end",
            "over_52_skipped_patients": "Over-52s skipped", "weeks_infeasible": "Weeks infeasible",
            "mean_wait_surgery": "Mean wait, surgery", "mean_oks_operated": "Mean OKS operated on"})
    md = [
        "# Weekly slots: 26-week simulation", "",
        f"Start: the cleaned waiting list, {len(start_el)} patients needing a slot "
        f"(surgery {int((start_el.pathway == 'surgery').sum())}, physio {int((start_el.pathway == 'physio').sum())}, "
        f"weight support and physio {int((start_el.pathway == 'weight_physio').sum())}); "
        f"{int((start_el.weeks_waiting > 52).sum())} already over 52 weeks. "
        f"New referrals: {rate:.1f} a week (Poisson; the rate implied by the generator's referral dates), "
        f"{sum(len(n) for n in new)} in 26 weeks, same for every policy. Slots a week: surgery 12, physio 20, "
        "weight support 8. Counts are of patients who need one of these slots.", "",
        "**Skipped** = an over-52 patient left without a slot while a slot they could use went to someone not over "
        "52. **Weeks over-52s didn't fit** = weeks the optimiser reported infeasible (it then gave every slot it "
        "could to over-52s; the rest were listed, not skipped).", "",
        "## Surgery capacity 12", "", fmt(table.T).to_markdown(), "",
        "![Backlog](backlog.png)", "",
        "In the over-52 panel FCFS and the optimiser are the same line: both clear the over-52s by week 7 and "
        "keep the count at zero (FCFS by always taking the longest wait, the optimiser by its hard rule).", "", "![Wait by pathway](wait_by_pathway.png)", "",
        "## Sensitivity: surgery capacity 8, 12, 16 a week", "", fmt(sens).to_markdown(index=False), "",
        "![Sensitivity](sensitivity.png)", "",
    ]
    (RESULTS / "optimise_summary.md").write_text("\n".join(md))
    series = weekly[(weekly.surgery_capacity == 12) & weekly.policy.isin(POLICIES)][
        ["policy", "week", "over_18", "over_52", "waiting"]]
    (RESULTS / "optimise_summary.json").write_text(json.dumps({
        "weeks": WEEKS, "arrival_rate": rate, "arrivals": sum(len(n) for n in new), "capacity": O.CAPACITY,
        "summary": summary.to_dict(orient="records"),
        "series": {p: series[series.policy == p].drop(columns="policy").to_dict(orient="records") for p in POLICIES},
    }, indent=1, default=lambda v: v.item() if hasattr(v, "item") else str(v)))
    print("\n".join(md[:8]))
    print(f"\nWrote {RESULTS.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
