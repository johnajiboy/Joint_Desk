"""Score LLM extraction against the answer key.

Reports per-field accuracy, quote hit rate and pathway agreement (rules on the extracted facts vs the gold
pathway), and writes tables to eval/results/. Weeks waiting comes from the waiting list, matched on the
NHS number the LLM read, as the app does.

    python eval/eval_extraction.py --limit 5 --show
    python eval/eval_extraction.py                                                  # dev set
    python eval/eval_extraction.py --data data/output/test --results eval/results/test  # held-out test set
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kneedss import extract as X           # noqa: E402
from kneedss import llm                    # noqa: E402
from kneedss.rules import PATHWAYS         # noqa: E402
from kneedss.schemas import FALSE_WITHOUT_QUOTE, FIELDS, SCORED_FIELDS  # noqa: E402

OUT = ROOT / "data" / "output"
RESULTS = ROOT / "eval" / "results"


def _text(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip()


def same(field: str, gold, got) -> bool:
    """Does the extracted value match the gold value? Both null counts as a match."""
    if gold is None or got is None:
        return gold is None and got is None
    if field == "name":
        return _text(gold) == _text(got)
    if field == "xray_finding":
        g, e = _text(gold), _text(got)
        return g in e or e in g
    if field == "bmi":
        return abs(float(gold) - float(got)) < 0.05
    return gold == got


def outcome(field: str, gold, got) -> str:
    if same(field, gold, got):
        return "correct"
    if gold is None:
        return "extra"
    if got is None:
        return "missed"
    return "wrong"


def nhs_digits(n) -> str:
    return re.sub(r"\D", "", str(n or ""))


def score_letter(key: dict, text: str, ex: X.Extraction, raw: dict, waiting: dict[str, int]) -> dict:
    fields = {f: outcome(f, key["gold"][f], ex.facts[f]) for f in SCORED_FIELDS}
    quoted = [f for f in FIELDS if raw[f]["value"] is not None
              and not (f in FALSE_WITHOUT_QUOTE and raw[f]["value"] is False and not raw[f]["quote"])]
    hits = [f for f in quoted if X.quote_in_letter(raw[f]["quote"], text)]
    weeks = waiting.get(nhs_digits(ex.facts["nhs_number"]))
    d = X.decide_letter(ex.facts, weeks)
    return {
        "letter_id": key["letter_id"], "style": key["style"], "tags": key["difficulty_tags"],
        "fields": fields, "quoted": len(quoted), "quote_hits": len(hits), "dropped": ex.dropped,
        "nhs_matched": weeks is not None,
        "gold_pathway": key["gold_pathway"], "pathway": d["pathway"], "rule": d["rule"],
        "reasons": d["reasons"], "gold_priority": key["gold_priority_score"], "priority": d["priority"],
        "errors": [{"letter_id": key["letter_id"], "field": f, "outcome": o, "gold": key["gold"][f],
                    "got": ex.facts[f], "quote": raw[f]["quote"]} for f, o in fields.items() if o != "correct"],
        "from_cache": ex.from_cache,
    }


def run_one(key: dict, text: str, waiting: dict[str, int], refresh: bool) -> dict:
    ex = X.extract(text, key["letter_id"], refresh=refresh)
    raw = json.loads(X.cache_path(key["letter_id"], ex.model).read_text())["raw"]
    return score_letter(key, text, ex, raw, waiting)


def show(r: dict) -> None:
    agree = "agree" if r["pathway"] == r["gold_pathway"] else f"gold {PATHWAYS[r['gold_pathway']]}"
    print(f"\n{r['letter_id']}  {PATHWAYS[r['pathway']]} · {r['priority']}  (rule {r['rule']}, {agree}; "
          f"gold priority {r['gold_priority']})")
    print(f"  why: {'; '.join(r['reasons'])}")
    print(f"  fields: {sum(o == 'correct' for o in r['fields'].values())}/{len(r['fields'])} correct, "
          f"quotes {r['quote_hits']}/{r['quoted']} found, NHS number {'matched' if r['nhs_matched'] else 'not matched'}")
    for e in r["errors"]:
        print(f"  {e['outcome']:7} {e['field']}: gold {e['gold']!r}, got {e['got']!r}  quote {e['quote']!r}")
    for d in r["dropped"]:
        print(f"  dropped {d['field']}={d['value']!r} ({d['reason']}): {d['quote']!r}")


def summarise(results: list[dict], failed: list[tuple[str, str]], model: str, seconds: float,
              out: Path = RESULTS, label: str = "dev") -> str:
    n = len(results)
    rows = []
    for f in SCORED_FIELDS:
        c = pd.Series([r["fields"][f] for r in results]).value_counts()
        rows.append({"field": f, "accuracy": c.get("correct", 0) / n, "correct": c.get("correct", 0),
                     "wrong": c.get("wrong", 0), "missed": c.get("missed", 0), "extra": c.get("extra", 0)})
    fields = pd.DataFrame(rows)
    fields.to_csv(out / "extraction_fields.csv", index=False)

    errors = pd.DataFrame([e for r in results for e in r["errors"]],
                          columns=["letter_id", "field", "outcome", "gold", "got", "quote"])
    errors.to_csv(out / "extraction_errors.csv", index=False)

    letters = pd.DataFrame([{k: r[k] for k in ("letter_id", "style", "gold_pathway", "pathway", "rule",
                                               "gold_priority", "priority", "nhs_matched")}
                            | {"tags": ";".join(r["tags"]),
                               "fields_correct": sum(o == "correct" for o in r["fields"].values())}
                            for r in results])
    letters.to_csv(out / "extraction_letters.csv", index=False)

    quoted, hits = sum(r["quoted"] for r in results), sum(r["quote_hits"] for r in results)
    agree = (letters.pathway == letters.gold_pathway)
    all_right = letters.fields_correct == len(SCORED_FIELDS)
    cm = pd.crosstab(letters.gold_pathway.map(PATHWAYS), letters.pathway.map(PATHWAYS),
                     rownames=["gold"], colnames=["from extraction"])
    tags = sorted({t for r in results for t in r["tags"]})
    by_tag = pd.DataFrame([{"tag": t, "letters": int(m.sum()), "pathway agreement": agree[m].mean(),
                            "all fields right": all_right[m].mean()}
                           for t in tags for m in [letters.tags.str.split(";").apply(lambda s, t=t: t in s)]])
    by_style = pd.DataFrame([{"style": s, "letters": int(m.sum()), "pathway agreement": agree[m].mean(),
                              "all fields right": all_right[m].mean()}
                             for s in sorted(letters.style.unique()) for m in [letters.style == s]])

    lines = [
        f"# Extraction evaluation: {label} set", "",
        f"Model: `{model}`. Letters scored: {n}" + (f" ({len(failed)} failed)" if failed else "") +
        f". Run time {seconds:.0f}s.", "",
        "| Measure | Value |", "|---|---|",
        f"| Mean field accuracy | {fields.accuracy.mean():.1%} |",
        f"| Letters with every field right | {all_right.mean():.1%} |",
        f"| Quote hit rate | {hits / max(quoted, 1):.1%} ({hits}/{quoted}) |",
        f"| Facts dropped by quote check | {sum(len(r['dropped']) for r in results)} |",
        f"| Pathway agreement | {agree.mean():.1%} ({int(agree.sum())}/{n}) |",
        f"| Priority score, mean absolute difference | {(letters.priority - letters.gold_priority).abs().mean():.1f} |",
        f"| NHS number matched to waiting list | {letters.nhs_matched.mean():.1%} |",
        "", "## Per-field accuracy", "",
        fields.to_markdown(index=False, floatfmt=".1%"),
        "", "## Pathway: gold vs from extraction", "", cm.to_markdown(),
        "", "## By difficulty tag", "", by_tag.to_markdown(index=False, floatfmt=".1%"),
        "", "## By letter style", "", by_style.to_markdown(index=False, floatfmt=".1%"),
    ]
    if failed:
        lines += ["", "## Failed", ""] + [f"- {lid}: {msg}" for lid, msg in failed]
    md = "\n".join(lines) + "\n"
    (out / "extraction_summary.md").write_text(md)
    headline = {
        "set": label, "model": model, "letters": n, "failed": len(failed),
        "mean_field_accuracy": fields.accuracy.mean(), "letters_all_fields_right": all_right.mean(),
        "quote_hit_rate": hits / max(quoted, 1), "facts_dropped": sum(len(r["dropped"]) for r in results),
        "pathway_agreement": agree.mean(),
        "priority_mae": (letters.priority - letters.gold_priority).abs().mean(),
        "nhs_matched": letters.nhs_matched.mean(),
        "field_accuracy": dict(zip(fields.field, fields.accuracy)),
    }
    (out / "extraction_summary.json").write_text(json.dumps(headline, indent=1, default=float))
    return md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="score only the first N letters")
    ap.add_argument("--ids", nargs="*", help="letter IDs to score")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and call the API again")
    ap.add_argument("--show", action="store_true", help="print each letter's result")
    ap.add_argument("--data", type=Path, default=OUT, help="letters and answer key (default data/output)")
    ap.add_argument("--results", type=Path, default=RESULTS, help="where to write tables (default eval/results)")
    a = ap.parse_args()
    label = "dev" if a.data.resolve() == OUT.resolve() else a.data.name

    keys = [json.loads(line) for line in open(a.data / "answer_key.jsonl")]
    texts = {d["letter_id"]: d["text"] for d in map(json.loads, open(a.data / "letters.jsonl"))}
    if a.ids:
        keys = [k for k in keys if k["letter_id"] in set(a.ids)]
    if a.limit:
        keys = keys[: a.limit]
    patients = pd.read_csv(OUT / "patients_clean.csv", dtype={"nhs_number": str})
    waiting = dict(zip(patients.nhs_number.map(nhs_digits), patients.weeks_waiting.astype(int)))

    a.results.mkdir(parents=True, exist_ok=True)
    model, start = llm.model_name(), time.time()
    results, failed = [], []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        jobs = {pool.submit(run_one, k, texts[k["letter_id"]], waiting, a.refresh): k["letter_id"] for k in keys}
        for i, job in enumerate(as_completed(jobs), 1):
            lid = jobs[job]
            try:
                results.append(job.result())
            except (llm.LLMError, X.DemoCacheMiss, ValueError) as e:
                failed.append((lid, str(e)))
            print(f"\r{i}/{len(keys)} letters", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    results.sort(key=lambda r: r["letter_id"])

    if a.show:
        for r in results:
            show(r)
        print()
    if results:
        print(summarise(results, failed, model, time.time() - start, a.results, label))
    for lid, msg in failed:
        print(f"FAILED {lid}: {msg}")


if __name__ == "__main__":
    main()
