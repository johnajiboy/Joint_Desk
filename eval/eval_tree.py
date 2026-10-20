"""Decision tree vs expert rules (stage 4). No API calls.

Checks first that the generator's true_pathway equals rules.decide() for every patient. Then trains the gated tree
on the raw-value features and on the discretised ones (70/30 stratified split, seed 2026, max_depth and
min_samples_leaf tuned by 5-fold CV on the training split), and compares each with the rules on the test split.

    python eval/eval_tree.py     -> eval/results/tree/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support  # noqa: E402
from sklearn.tree import export_text, plot_tree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import tree as T              # noqa: E402
from kneedss.rules import PATHWAYS         # noqa: E402

OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results" / "tree"
ORDER = ["surgery", "physio", "weight_physio", "non_surgical", "review"]
KEY_COLS = ["patient_id", "oks", "oks_before", "kl_grade", "bmi", "physio_weeks", "weeks_waiting"]


def evaluate(name: str, g: T.GatedTree, test: pd.DataFrame) -> dict:
    pred = g.predict(test)
    rules = test.pathway
    full = T.complete(test)
    p, r, f1, n = precision_recall_fscore_support(rules, pred, labels=ORDER, zero_division=0)
    per_class = pd.DataFrame({"pathway": [PATHWAYS[k] for k in ORDER], "precision": p, "recall": r, "f1": f1,
                              "patients": n})
    cm = pd.DataFrame(confusion_matrix(rules, pred, labels=ORDER),
                      index=[PATHWAYS[k] for k in ORDER], columns=[PATHWAYS[k] for k in ORDER])
    cm.index.name, cm.columns.name = "rules", "tree"
    dis = test[pred != rules][KEY_COLS].assign(
        oks_drop=lambda d: d.oks_before - d.oks, rules=rules[pred != rules].map(PATHWAYS),
        rule=test.rule[pred != rules], tree=pred[pred != rules].map(PATHWAYS), model=name)
    thresholds = T.compare_thresholds(g.model, g.names)
    imp = T.importances(g.model, g.names)

    tag = "" if name == "continuous" else f"_{name}"
    (RESULTS / f"tree_rules{tag}.txt").write_text(export_text(g.model, feature_names=g.names, decimals=2))
    fig, ax = plt.subplots(figsize=(20, 9))
    plot_tree(g.model, feature_names=g.names, class_names=[PATHWAYS[c] for c in g.model.classes_],
              impurity=False, proportion=False, rounded=True, fontsize=7, ax=ax)
    ax.set_title(f"Decision tree ({name} features): depth {g.model.get_depth()}, {T.leaf_count(g.model)} leaves")
    fig.savefig(RESULTS / f"tree{tag}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    per_class.to_csv(RESULTS / f"per_pathway{tag}.csv", index=False)
    cm.to_csv(RESULTS / f"confusion{tag}.csv")
    thresholds.to_csv(RESULTS / f"thresholds{tag}.csv", index=False)
    imp.rename("importance").to_csv(RESULTS / f"importances{tag}.csv", index_label="feature")
    g.cv.to_csv(RESULTS / f"cv{tag}.csv", index=False)

    return {
        "name": name, "features": g.names, "best_params": g.best_params, "cv_accuracy": g.cv_accuracy,
        "depth": g.model.get_depth(), "leaves": T.leaf_count(g.model),
        "test_patients": len(test), "test_complete": int(full.sum()),
        "agreement": float((pred == rules).mean()),
        "agreement_complete": float((pred[full] == rules[full]).mean()),
        "per_class": per_class, "confusion": cm, "thresholds": thresholds, "importances": imp, "disagreements": dis,
    }


def extra_note(r: dict) -> str:
    """Splits that aren't a rule cut: the tree puts its line halfway between the nearest patients on either side,
    so where no patient sits near the rule's value, any cut in that gap fits the data equally well."""
    rule_cuts = {(x["feature"], x["tree_nearest"]) for x in r["thresholds"].to_dict(orient="records") if x["same_cut"]}
    extra = [f"{x['feature']} <= {s}" for x in r["thresholds"].drop_duplicates("feature").to_dict(orient="records")
             for s in map(float, x["tree_splits"].split(", ")) if x["tree_splits"] != "not used"
             and (x["feature"], s) not in rule_cuts]
    if not extra:
        return "Every learned split on these features is a rule cut."
    if r["name"] != "continuous":
        return ("Extra splits that are not rule cuts: " + ", ".join(extra) + ". A band split can only fall on a band "
                "edge, so the OKS band edge at 29 stands in for the rules' 26: patients with OKS 27-29 and KL 3+ are "
                f"where the {len(r['disagreements'])} disagreements come from. Any other extra split either leads to "
                "the same pathway on both sides or sits in a gap between patients.")
    return ("Extra splits that are not rule cuts: " + ", ".join(extra) + ". The tree splits halfway between the "
            "nearest patients either side; where nobody sits near the rule's value, any cut in that gap fits the "
            "data equally well, so these agree with the rules on every patient but are not the rules' numbers.")


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    truth = T.check_truth(pd.read_csv(OUT / "patients_clean.csv"))
    df = pd.read_csv(OUT / "waiting_list.csv")
    train, test = T.split(df)
    runs = [evaluate("continuous", T.GatedTree(False).fit(train), test),
            evaluate("discretised", T.GatedTree(True).fit(train), test)]
    dis = pd.concat([r["disagreements"] for r in runs])
    dis.to_csv(RESULTS / "disagreements.csv", index=False)

    md = [
        "# Decision tree vs expert rules", "",
        f"Truth check: `true_pathway` in patients_clean.csv equals `rules.decide()` (pathway and rule) for "
        f"**{truth['matching']} of {truth['patients']}** patients"
        + (f"; mismatches: {', '.join(truth['mismatches'])}." if truth["mismatches"] else "."), "",
        "The label is the pathway the rules give on the cleaned table, so agreement shows how much of the expert "
        "rules the tree recovers from data. Missing OKS, X-ray grade or physio goes to review before the tree, as "
        f"in rule 1. Split: {len(train)} train / {len(test)} test, stratified, seed {T.SEED}; max_depth 2-8 and "
        "min_samples_leaf 1-20 tuned by 5-fold CV on the training split.", "",
        "| | Raw values | Discretised (OKS bands, BMI categories, wait bands) |", "|---|---|---|",
        *[f"| {label} | {fmt(runs[0])} | {fmt(runs[1])} |" for label, fmt in [
            ("Best max_depth / min_samples_leaf", lambda r: f"{r['best_params']['max_depth']} / {r['best_params']['min_samples_leaf']}"),
            ("CV accuracy (train, complete records)", lambda r: f"{r['cv_accuracy']:.1%}"),
            ("Depth / leaves", lambda r: f"{r['depth']} / {r['leaves']}"),
            ("Agreement with rules, test split", lambda r: f"**{r['agreement']:.1%}** ({r['test_patients']})"),
            ("Agreement, complete records only", lambda r: f"{r['agreement_complete']:.1%} ({r['test_complete']})"),
            ("Disagreements", lambda r: f"{len(r['disagreements'])}"),
        ]],
    ]
    for r in runs:
        md += [
            "", f"## {r['name'].capitalize()} features", "",
            "### Per pathway (rules as reference)", "", r["per_class"].to_markdown(index=False, floatfmt=".3f"), "",
            "### Confusion matrix", "", r["confusion"].to_markdown(), "",
            "### Rule thresholds vs learned splits", "",
            "A split at `<= t` is the same cut as the rule when t lies between the rule value and the next possible "
            "value (whole numbers; BMI to 0.1)." + (" Band splits are shown as the raw value at the band edge." if r["name"] != "continuous" else ""),
            "", r["thresholds"].to_markdown(index=False), "",
            extra_note(r), "",
            "### Feature importance", "", r["importances"].rename("importance").to_frame().to_markdown(floatfmt=".3f"), "",
            f"### Learned tree (`tree_rules{'' if r['name'] == 'continuous' else '_' + r['name']}.txt`)", "",
            "```", (RESULTS / f"tree_rules{'' if r['name'] == 'continuous' else '_' + r['name']}.txt").read_text().rstrip(), "```",
        ]
    md += ["", "## Disagreements on the test split", ""]
    md += [dis.drop(columns=["oks_before"]).to_markdown(index=False) if len(dis) else "None."]
    (RESULTS / "tree_summary.md").write_text("\n".join(md) + "\n")

    def jsonable(r: dict) -> dict:
        return {k: (v.to_dict(orient="records") if isinstance(v, pd.DataFrame) and k != "confusion"
                    else v.to_dict() if isinstance(v, (pd.Series, pd.DataFrame)) else v) for k, v in r.items()}
    (RESULTS / "tree_summary.json").write_text(json.dumps(
        {"truth_check": truth, "train": len(train), "test": len(test), "seed": T.SEED,
         "runs": [jsonable(r) for r in runs]}, indent=1, default=lambda v: v.item() if hasattr(v, "item") else str(v)))
    print("\n".join(md[:12]))
    print(f"\nWrote {RESULTS.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
