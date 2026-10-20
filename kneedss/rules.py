"""Reference pathway rules and surgical priority score.

A simplified reading of NICE NG226 (Osteoarthritis in over 16s, 2022). These are the SAME rules the
decision system uses, applied here to the true facts to produce the gold-standard pathway in the
answer key. They need clinical sign-off before any real use.

Facts use these keys (None = not known):
  oks, oks_before, kl, physio_weeks, bmi, weeks_waiting, night_pain, lives_alone_or_carer
"""
from __future__ import annotations

PATHWAYS = {
    "review": "Ask the GP for more information",
    "weight_physio": "Weight support and physio first",
    "physio": "Physio first",
    "surgery": "Surgery list",
    "non_surgical": "Keep on non-surgical care",
}

PHYSIO_MIN_WEEKS = 6       # NICE: offer therapeutic exercise before considering referral for surgery
OKS_SEVERE_MAX = 19        # Oxford Knee Score 0-19 = severe
OKS_SURGERY_MAX = 26       # score at or below which surgery is considered with KL 3-4
BMI_WEIGHT_SUPPORT = 35    # BMI threshold for offering weight management support
FAST_DECLINE = 5           # points lost since the earlier score


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def decide(f: dict) -> dict:
    """Return {'pathway', 'rule', 'reasons', 'weight_support'}."""
    oks, before, kl, physio, bmi = f.get("oks"), f.get("oks_before"), f.get("kl"), f.get("physio_weeks"), f.get("bmi")
    reasons = []
    if _missing(oks) or _missing(kl) or _missing(physio):
        if _missing(oks): reasons.append("No Oxford Knee Score")
        if _missing(kl): reasons.append("No X-ray grade")
        if _missing(physio): reasons.append("Physiotherapy history unclear")
        return {"pathway": "review", "rule": 1, "reasons": reasons, "weight_support": False}
    drop = 0 if _missing(before) else before - oks
    high_bmi = not _missing(bmi) and bmi >= BMI_WEIGHT_SUPPORT
    if physio < PHYSIO_MIN_WEEKS and oks > OKS_SEVERE_MAX:
        reasons += [f"Physio {physio} weeks (under {PHYSIO_MIN_WEEKS})", f"OKS {oks} above severe range"]
        if high_bmi:
            return {"pathway": "weight_physio", "rule": 2, "reasons": reasons + [f"BMI {bmi}"], "weight_support": True}
        return {"pathway": "physio", "rule": 3, "reasons": reasons, "weight_support": False}
    if oks <= OKS_SURGERY_MAX and kl >= 3:
        reasons += [f"OKS {oks}", f"KL grade {kl}", f"Physio {physio} weeks"]
        return {"pathway": "surgery", "rule": 4, "reasons": reasons, "weight_support": high_bmi}
    if drop >= FAST_DECLINE and kl >= 3:
        reasons += [f"OKS down {drop} points", f"KL grade {kl}"]
        return {"pathway": "surgery", "rule": 5, "reasons": reasons, "weight_support": high_bmi}
    reasons += [f"OKS {oks} with KL grade {kl} does not indicate surgery yet"]
    return {"pathway": "non_surgical", "rule": 6, "reasons": reasons, "weight_support": False}


def priority_score(f: dict) -> int:
    """0-100. Pain/function (48) + X-ray damage (20) + decline (16) + time waiting (16) + social (8), scaled."""
    oks, before, kl = f.get("oks"), f.get("oks_before"), f.get("kl")
    weeks = f.get("weeks_waiting") or 0
    pts = 0
    pts += 0 if _missing(oks) else 48 - oks
    pts += 0 if _missing(kl) else kl * 5
    pts += 0 if (_missing(oks) or _missing(before)) else min(16, max(0, (before - oks) * 2))
    pts += round(min(weeks, 78) / 78 * 16)
    pts += (4 if f.get("night_pain") else 0) + (4 if f.get("lives_alone_or_carer") else 0)
    return round(pts / 108 * 100)
