"""Apply the pre-registered BIRD rules of SPEC 8 and write results/bird_hypotheses.json.

O1 (transfer): C3 minus C1 on BIRD dev EX (with evidence) >= 2 pp and lower 95% CI bound > 0.
O2 (no harm): lower 95% CI bound of C3 minus C1 >= -2 pp.
Per size; C3 is the seed average of 3 runs (fewer: EXPLORATORY). Primary interval: db-cluster
bootstrap (11 databases); per-question bootstrap reported as a sensitivity check only.
Questions whose gold fails in any run score 0 in all runs.
Secondary, no thresholds: evidence effect (with minus without, C1 and C3 seed 0), contamination
probe (C1 Spider dev EX vs BIRD dev EX), accuracy by difficulty.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from spider_sql.stats import Key, load_rows, mcnemar_exact, paired_cluster_bootstrap, seed_average

LR, EPOCHS, SEEDS = "0.0002", 2, (0, 1, 2)
SIZES = ("qwen05b", "qwen15b")
O1_MIN_GAIN, O2_MIN_LOWER = 0.02, -0.02


def c3_runs(tag: str) -> list[str]:
    return [f"{tag}_c3_lr{LR}_ep{EPOCHS}_seed{s}" for s in SEEDS]


def decide_o1(diff: dict[str, float], n_seeds: int) -> str:
    if n_seeds < 3:
        return "EXPLORATORY"
    return "SUCCESS" if diff["point"] >= O1_MIN_GAIN and diff["lo"] > 0 else "NOT MET"


def decide_o2(diff: dict[str, float], n_seeds: int) -> str:
    if n_seeds < 3:
        return "EXPLORATORY"
    return "SUCCESS" if diff["lo"] >= O2_MIN_LOWER else "NOT MET"


def diff(
    a: list[dict[Key, dict[str, object]]],
    b: list[dict[Key, dict[str, object]]],
    by_question: bool = False,
) -> dict[str, float]:
    clusters = {k: (f"{k[0]}:{k[1]}" if by_question else str(v["db_id"])) for k, v in a[0].items()}
    return paired_cluster_bootstrap(seed_average(a, "ex"), seed_average(b, "ex"), clusters)


def accuracy(rows: dict[Key, dict[str, object]], metric: str = "ex") -> float:
    return sum(int(str(r[metric])) for r in rows.values()) / len(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results"))
    args = parser.parse_args(argv)

    def read(run: str, variant: str = "bird_dev") -> dict[Key, dict[str, object]]:
        return load_rows(args.results / run / f"{variant}.jsonl")

    # A gold query that fails in any run (error, or a 30 s timeout that depends on machine
    # load) scores 0 in every run, so all comparisons stay paired (docs/DECISIONS.md).
    gold_failed: set[Key] = set()
    for path in args.results.glob("*/bird_dev*.jsonl"):
        gold_failed |= {k for k, v in load_rows(path).items() if v["ex_reason"] == "gold_error"}

    def load(run: str, variant: str = "bird_dev") -> dict[Key, dict[str, object]]:
        rows = read(run, variant)
        for k in gold_failed & rows.keys():
            rows[k] = {**rows[k], "ex": 0}
        return rows

    out: dict[str, object] = {
        "rules": "SPEC 8",
        "O1": f"gain >= {100 * O1_MIN_GAIN:g} pp and lower bound > 0",
        "O2": f"lower bound >= {100 * O2_MIN_LOWER:g} pp",
        "gold_failed": sorted(f"{k[0]}:{k[1]}" for k in gold_failed),
    }
    for tag in SIZES:
        c1_run = f"{tag}_c1_zero_shot"
        seeds = [r for r in c3_runs(tag) if (args.results / r / "bird_dev.jsonl").is_file()]
        c1, c3 = [load(c1_run)], [load(r) for r in seeds]
        primary = diff(c1, c3)
        sensitivity = diff(c1, c3, by_question=True)
        entry: dict[str, object] = {
            "c3_runs": seeds,
            "c1_ex": accuracy(c1[0]),
            "c3_ex_per_seed": [accuracy(r) for r in c3],
            "c3_minus_c1": primary,
            "O1": decide_o1(primary, len(seeds)),
            "O2": decide_o2(primary, len(seeds)),
            "sensitivity_per_question": {
                "c3_minus_c1": sensitivity,
                "O1": decide_o1(sensitivity, len(seeds)),
                "O2": decide_o2(sensitivity, len(seeds)),
            },
            "mcnemar_per_seed": [
                mcnemar_exact(
                    {k: int(str(v["ex"])) for k, v in c1[0].items()},
                    {k: int(str(v["ex"])) for k, v in r.items()},
                )
                for r in c3
            ],
        }
        evidence = {}
        for run in (c1_run, seeds[0] if seeds else None):
            if run and (args.results / run / "bird_dev_noev.jsonl").is_file():
                evidence[run] = diff([load(run, "bird_dev_noev")], [load(run)])
        entry["evidence_effect_with_minus_without"] = evidence
        spider_dev = args.results / c1_run / "dev.jsonl"
        if spider_dev.is_file():
            entry["contamination_probe"] = {
                "c1_spider_dev_ex": accuracy(load_rows(spider_dev)),
                "c1_bird_dev_ex": accuracy(c1[0]),
                "note": "different benchmarks and metrics; a gap is a limitation, not corrected",
            }
        out[tag] = entry
        print(
            f"{tag}: C1 {100 * accuracy(c1[0]):.2f}  C3 seeds "
            + " / ".join(f"{100 * accuracy(r):.2f}" for r in c3)
            + f"  C3-C1 {100 * primary['point']:+.2f} pp "
            f"[{100 * primary['lo']:+.2f}, {100 * primary['hi']:+.2f}]  "
            f"O1 {entry['O1']}  O2 {entry['O2']}  "
            f"(per-question CI [{100 * sensitivity['lo']:+.2f}, {100 * sensitivity['hi']:+.2f}])"
        )
    path = args.results / "bird_hypotheses.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
