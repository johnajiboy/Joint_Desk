"""Dev vs held-out test extraction results, side by side.

    python eval/compare_sets.py     -> prints the table, writes eval/results/dev_vs_test.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RESULTS = Path(__file__).resolve().parent / "results"

HEADLINE = [
    ("letters", "Letters", "{:.0f}"), ("mean_field_accuracy", "Mean field accuracy", "{:.1%}"),
    ("letters_all_fields_right", "Letters with every field right", "{:.1%}"),
    ("quote_hit_rate", "Quote hit rate", "{:.1%}"), ("facts_dropped", "Facts dropped by quote check", "{:.0f}"),
    ("pathway_agreement", "Pathway agreement", "{:.1%}"), ("priority_mae", "Priority score, mean abs. difference", "{:.1f}"),
    ("nhs_matched", "NHS number matched", "{:.1%}"),
]


def main() -> None:
    dev = json.loads((RESULTS / "extraction_summary.json").read_text())
    test = json.loads((RESULTS / "test" / "extraction_summary.json").read_text())
    head = pd.DataFrame([{"Measure": name, "Dev (150, tuned on)": fmt.format(dev[k]),
                          "Test (100, held out, hard)": fmt.format(test[k])} for k, name, fmt in HEADLINE])
    fields = pd.DataFrame({"Dev": dev["field_accuracy"], "Test": test["field_accuracy"]})
    fields["Change"] = fields.Test - fields.Dev
    models = {dev["model"], test["model"]}
    md = "\n".join([
        "# Extraction: dev vs held-out test", "",
        f"Model: {', '.join(f'`{m}`' for m in sorted(models))}. The prompt was tuned on the dev set only; "
        "the test set uses new patients and harder letters (shorthand, typos, reordering, scanned text).", "",
        head.to_markdown(index=False), "", "## Per-field accuracy", "",
        fields.to_markdown(floatfmt=".1%"), "",
    ])
    (RESULTS / "dev_vs_test.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
