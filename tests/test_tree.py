import numpy as np
import pandas as pd
import pytest
from sklearn.tree import DecisionTreeClassifier

from kneedss import tree as T
from kneedss.clean import ROOT

OUT = ROOT / "data" / "output"


def row(**kw):
    base = {"oks": 22.0, "oks_before": 25, "kl_grade": 3.0, "bmi": 31.0, "physio_weeks": 8.0, "weeks_waiting": 20,
            "night_pain": True, "lives_alone_or_carer": False, "age": 70, "sex_code": 2, "oks_band": "moderate to severe",
            "bmi_category": "Obese I", "wait_band": "19-52 weeks", "pathway": "surgery"}
    return {**base, **kw}


@pytest.fixture(scope="module")
def data():
    df = pd.read_csv(OUT / "waiting_list.csv")
    train, test = T.split(df)
    return df, train, test


@pytest.fixture(scope="module")
def trees(data):
    _, train, _ = data
    return T.GatedTree(False).fit(train), T.GatedTree(True).fit(train)


def test_features_handle_missing_bmi_like_the_rules():
    x = T.features(pd.DataFrame([row(bmi=np.nan), row()]))
    assert list(x.columns) == T.FEATURES
    assert x.bmi.tolist() == [0.0, 31.0] and x.oks_drop.tolist() == [3.0, 3.0] and x.female.tolist() == [1, 1]


def test_banded_features_are_ordinal_codes():
    x = T.features(pd.DataFrame([row(), row(oks_band="severe", bmi_category=np.nan, wait_band="Over 52 weeks")]), banded=True)
    assert list(x.columns) == T.BANDED
    assert x.oks_band.tolist() == [1.0, 0.0] and x.bmi_category.tolist() == [4.0, 0.0] and x.wait_band.tolist() == [1.0, 2.0]


def test_missing_oks_kl_or_physio_goes_to_review(trees):
    g, _ = trees
    df = pd.DataFrame([row(oks=np.nan), row(kl_grade=np.nan), row(physio_weeks=np.nan), row(oks=10.0, kl_grade=4.0)])
    assert g.predict(df).tolist() == ["review", "review", "review", "surgery"]


def test_split_is_stratified_and_repeatable(data):
    df, train, test = data
    assert len(test) == round(len(df) * 0.3) and not set(train.patient_id) & set(test.patient_id)
    share = lambda d: d.pathway.value_counts(normalize=True)
    assert (share(train) - share(test)).abs().max() < 0.01
    assert T.split(df)[1].patient_id.tolist() == test.patient_id.tolist()


def test_tuning_uses_the_grid_and_training_split_only(trees, data):
    g, _ = trees
    _, train, _ = data
    assert g.best_params["max_depth"] in range(2, 9) and g.best_params["min_samples_leaf"] in T.GRID["min_samples_leaf"]
    assert len(g.cv) == 7 * len(T.GRID["min_samples_leaf"])
    assert g.model.tree_.n_node_samples[0] == int(T.complete(train).sum())     # fitted on complete training rows


def test_raw_value_tree_recovers_the_rules(trees, data):
    g, _ = trees
    _, _, test = data
    assert (g.predict(test) == test.pathway).mean() == 1.0
    assert T.compare_thresholds(g.model, g.names).same_cut.all()


def test_banded_tree_loses_only_where_bands_cannot_draw_oks_26(trees, data):
    g, b = trees
    _, _, test = data
    pred = b.predict(test)
    wrong = test[pred != test.pathway]
    assert 0 < len(wrong) and (pred == test.pathway).mean() < (g.predict(test) == test.pathway).mean()
    assert wrong.oks.between(27, 29).all() and (wrong.kl_grade >= 3).all()
    t = T.compare_thresholds(b.model, b.names).set_index("rule")
    assert t.loc["OKS 26 or less (with KL 3+) -> surgery", "tree_nearest"] == 29


def test_threshold_equivalence_on_a_known_split():
    x = pd.DataFrame({"oks": np.arange(0, 49, dtype=float)})
    y = np.where(x.oks <= 26, "surgery", "non_surgical")
    m = DecisionTreeClassifier(max_depth=1, random_state=0).fit(x, y)
    names = ["oks"]
    assert T.learned_thresholds(m, names) == {"oks": [26.5]}
    t = T.compare_thresholds(m, names).set_index("rule")
    assert t.loc["OKS 26 or less (with KL 3+) -> surgery", "same_cut"]
    assert not t.loc["OKS above 19 (severe 0-19) -> physio first", "same_cut"]
    assert t.loc["KL grade 3 or more", "tree_splits"] == "not used"


def test_band_splits_translate_to_raw_cuts():
    assert T.as_raw_cut("oks_band", 0.5) == ("oks", 19.0)
    assert T.as_raw_cut("oks_band", 1.5) == ("oks", 29.0)
    assert T.as_raw_cut("bmi_category", 4.5) == ("bmi", 34.9)
    assert T.as_raw_cut("wait_band", 1.5) == ("weeks_waiting", 52.0)
    assert T.as_raw_cut("kl_grade", 2.5) == ("kl_grade", 2.5)


def test_truth_pathway_equals_the_rules_for_every_patient():
    check = T.check_truth(pd.read_csv(OUT / "patients_clean.csv"))
    assert check["matching"] == check["patients"] == 1500 and check["mismatches"] == []
