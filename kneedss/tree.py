"""Knowledge extraction: learn the pathway with a decision tree and compare it with the expert rules.

The label is the pathway rules.py gives on the cleaned table, so the question is how much of the expert rules a
tree can recover from data alone, and where it draws its lines. Missing values are handled as the rules handle
them: no Oxford score, X-ray grade or physio history means "review" (ask the GP) before any tree is consulted, so
the tree learns the other four pathways from complete records. A missing BMI counts as below 35, as in the rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.tree import DecisionTreeClassifier

from kneedss.clean import BMI_CATEGORIES, WAIT_BANDS
from kneedss.standards import OKS_BANDS

SEED = 2026
TEST_SIZE = 0.3
GRID = {"max_depth": list(range(2, 9)), "min_samples_leaf": [1, 2, 5, 10, 20]}

FEATURES = ["oks", "kl_grade", "bmi", "physio_weeks", "oks_drop", "weeks_waiting", "night_pain",
            "lives_alone_or_carer", "age", "female"]
# The discretised version swaps OKS, BMI and weeks waiting for their bands (ordinal codes, lowest first).
BANDED = ["oks_band", "kl_grade", "bmi_category", "physio_weeks", "oks_drop", "wait_band", "night_pain",
          "lives_alone_or_carer", "age", "female"]
OKS_BAND_CODE = {name: i for i, (_, _, name) in enumerate(OKS_BANDS)}
BMI_CODE = {name: i + 1 for i, (_, _, name) in enumerate(BMI_CATEGORIES)}       # 0 = missing (below every band)
WAIT_CODE = {name: i for i, (_, _, name) in enumerate(WAIT_BANDS)}

GATE = ["oks", "kl_grade", "physio_weeks"]                                      # missing any -> review (rule 1)

# The expert rules' cut points (rules.py), written the way a tree splits: "feature <= t" goes left.
RULE_THRESHOLDS = [
    {"rule": "OKS 26 or less (with KL 3+) -> surgery", "feature": "oks", "threshold": 26, "step": 1},
    {"rule": "OKS above 19 (severe 0-19) -> physio first", "feature": "oks", "threshold": 19, "step": 1},
    {"rule": "KL grade 3 or more", "feature": "kl_grade", "threshold": 2, "step": 1},
    {"rule": "BMI 35 or more -> weight support", "feature": "bmi", "threshold": 34.9, "step": 0.1},
    {"rule": "Physio under 6 weeks", "feature": "physio_weeks", "threshold": 5, "step": 1},
    {"rule": "OKS drop of 5 or more", "feature": "oks_drop", "threshold": 4, "step": 1},
]


def complete(df: pd.DataFrame) -> pd.Series:
    """Rows the tree decides; the rest go to review, as in rule 1."""
    return df[GATE].notna().all(axis=1)


def features(df: pd.DataFrame, banded: bool = False) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["oks"] = df.oks.astype(float)
    x["kl_grade"] = df.kl_grade.astype(float)
    x["bmi"] = df.bmi.astype(float).fillna(0.0)                  # missing BMI = not 35 or more, as in the rules
    x["physio_weeks"] = df.physio_weeks.astype(float)
    x["oks_drop"] = (df.oks_before - df.oks).astype(float)
    x["weeks_waiting"] = df.weeks_waiting.astype(float)
    x["night_pain"] = df.night_pain.astype(bool).astype(int)
    x["lives_alone_or_carer"] = df.lives_alone_or_carer.astype(bool).astype(int)
    x["age"] = df.age.astype(float)
    x["female"] = (df.sex_code == 2).astype(int)
    if not banded:
        return x[FEATURES]
    x["oks_band"] = df.oks_band.map(OKS_BAND_CODE).astype(float)
    x["bmi_category"] = df.bmi_category.map(BMI_CODE).fillna(0).astype(float)
    x["wait_band"] = df.wait_band.map(WAIT_CODE).astype(float)
    return x[BANDED]


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified 70/30 split on the pathway, seed 2026."""
    train, test = train_test_split(df, test_size=TEST_SIZE, stratify=df.pathway, random_state=SEED)
    return train, test


@dataclass
class GatedTree:
    """Rule 1 gate, then a tuned decision tree for complete records."""
    banded: bool = False
    model: DecisionTreeClassifier | None = None
    cv: pd.DataFrame = field(default_factory=pd.DataFrame)
    best_params: dict = field(default_factory=dict)
    cv_accuracy: float = 0.0

    @property
    def names(self) -> list[str]:
        return BANDED if self.banded else FEATURES

    def fit(self, train: pd.DataFrame) -> "GatedTree":
        rows = train[complete(train)]
        search = GridSearchCV(DecisionTreeClassifier(random_state=SEED), GRID, scoring="accuracy",
                              cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
        search.fit(features(rows, self.banded), rows.pathway)
        self.model, self.best_params, self.cv_accuracy = search.best_estimator_, search.best_params_, search.best_score_
        cv = pd.DataFrame(search.cv_results_)
        self.cv = cv[["param_max_depth", "param_min_samples_leaf", "mean_test_score", "std_test_score", "rank_test_score"]]
        return self

    def predict(self, df: pd.DataFrame) -> pd.Series:
        out = pd.Series("review", index=df.index, dtype=object)
        mask = complete(df)
        if mask.any():
            out[mask] = self.model.predict(features(df[mask], self.banded))
        return out


def learned_thresholds(model: DecisionTreeClassifier, names: list[str]) -> dict[str, list[float]]:
    """Every split point the tree uses, per feature."""
    t = model.tree_
    out: dict[str, list[float]] = {}
    for node in range(t.node_count):
        if t.children_left[node] != t.children_right[node]:
            out.setdefault(names[t.feature[node]], []).append(round(float(t.threshold[node]), 3))
    return {k: sorted(set(v)) for k, v in out.items()}


def as_raw_cut(feature: str, t: float) -> tuple[str, float]:
    """A split on a band code, written as the cut on the raw value it stands for (e.g. OKS band <= 1.5 is
    OKS <= 29, BMI category <= 4.5 is BMI <= 34.9)."""
    k = int(np.floor(t))
    if feature == "oks_band":
        return "oks", float(OKS_BANDS[k][1])
    if feature == "bmi_category":
        return "bmi", round(BMI_CATEGORIES[k - 1][1] - 0.1, 1) if k >= 1 else 0.0
    if feature == "wait_band":
        return "weeks_waiting", float(WAIT_BANDS[k][1])
    return feature, t


def compare_thresholds(model: DecisionTreeClassifier, names: list[str]) -> pd.DataFrame:
    """Each rule cut point next to the nearest split the tree learned on that feature.

    Values are whole numbers (BMI to 0.1), so a tree split at t is the same cut as the rule's when it falls
    between the rule threshold and the next possible value: e.g. OKS <= 26.5 is OKS <= 26. Band splits are
    translated back to raw values first."""
    learned: dict[str, list[float]] = {}
    for feature, splits in learned_thresholds(model, names).items():
        for t in splits:
            raw, cut = as_raw_cut(feature, t)
            learned.setdefault(raw, []).append(cut)
    learned = {k: sorted(set(v)) for k, v in learned.items()}
    rows = []
    for r in RULE_THRESHOLDS:
        splits = learned.get(r["feature"], [])
        nearest = min(splits, key=lambda s: abs(s - r["threshold"]), default=None)
        same = nearest is not None and r["threshold"] <= nearest < r["threshold"] + r["step"]
        rows.append({"rule": r["rule"], "feature": r["feature"], "rule_cut": f"<= {r['threshold']}",
                     "tree_nearest": nearest, "tree_splits": ", ".join(f"{s:g}" for s in splits) or "not used",
                     "same_cut": same})
    return pd.DataFrame(rows)


def check_truth(truth: pd.DataFrame) -> dict:
    """Does the generator's true_pathway equal rules.decide() on the true facts, for every patient?"""
    from kneedss.rules import decide
    bad = []
    for p in truth.itertuples():
        f = {"oks": p.oks, "oks_before": p.oks_before, "kl": p.kl_grade, "physio_weeks": p.physio_weeks, "bmi": p.bmi,
             "weeks_waiting": p.weeks_waiting, "night_pain": p.night_pain,
             "lives_alone_or_carer": bool(p.lives_alone or p.carer)}
        d = decide(f)
        if d["pathway"] != p.true_pathway or d["rule"] != p.true_rule:
            bad.append(p.patient_id)
    return {"patients": len(truth), "matching": len(truth) - len(bad), "mismatches": bad}


def importances(model: DecisionTreeClassifier, names: list[str]) -> pd.Series:
    return pd.Series(model.feature_importances_, index=names).sort_values(ascending=False)


def leaf_count(model: DecisionTreeClassifier) -> int:
    return int(np.sum(model.tree_.children_left == -1))
