"""Apply the pre-registered decision rules of SPEC 7.3 to the test results.

H1 (0.5B): C3 beats C1, mean gain >= 5 pp and lower 95% CI bound > 0.
H2 (1.5B): same with >= 3 pp. Metric: EX on Spider test; C3 is the seed average of 3 runs.
Fewer than 3 C3 runs make the hypothesis exploratory. Secondary comparisons have no threshold.
Writes results/hypotheses.json.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from spider_sql.stats import load_rows, paired_cluster_bootstrap, seed_average

LR, EPOCHS, SEEDS = "0.0002", 2, (0, 1, 2)
HYPOTHESES = {"H1": ("qwen05b", 0.05), "H2": ("qwen15b", 0.03)}
PRIMARY_METRIC = "ex"
SECONDARY_METRICS = ("ex_strict",)


def c3_runs(tag: str) -> list[str]:
    return [f"{tag}_c3_lr{LR}_ep{EPOCHS}_seed{s}" for s in SEEDS]


def decide(diff: dict[str, float], threshold: float, n_seeds: int) -> str:
    if n_seeds < 3:
        return "EXPLORATORY"
    return "SUCCESS" if diff["point"] >= threshold and diff["lo"] > 0 else "NOT MET"


def compare(results: Path, a: list[str], b: list[str], metric: str) -> dict[str, float]:
    a_rows = [load_rows(results / r / "test.jsonl") for r in a]
    b_rows = [load_rows(results / r / "test.jsonl") for r in b]
    clusters = {k: str(v["db_id"]) for k, v in a_rows[0].items()}
    return paired_cluster_bootstrap(
        seed_average(a_rows, metric), seed_average(b_rows, metric), clusters
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results"))
    args = parser.parse_args(argv)
    out: dict[str, object] = {"rules": "SPEC 7.3", "primary_metric": PRIMARY_METRIC}
    for name, (tag, threshold) in HYPOTHESES.items():
        c1 = [f"{tag}_c1_zero_shot"]
        c2 = [f"{tag}_c2_three_shot"]
        c3 = [r for r in c3_runs(tag) if (args.results / r / "test.jsonl").is_file()]
        primary = compare(args.results, c1, c3, PRIMARY_METRIC)
        outcome = decide(primary, threshold, len(c3))
        secondary = {f"c3_vs_c1_{m}": compare(args.results, c1, c3, m) for m in SECONDARY_METRICS}
        secondary["c3_vs_c2_ex"] = compare(args.results, c2, c3, "ex")
        secondary["c2_vs_c1_ex"] = compare(args.results, c1, c2, "ex")
        out[name] = {
            "model": tag,
            "threshold_pp": 100 * threshold,
            "c3_runs": c3,
            "c3_minus_c1": primary,
            "outcome": outcome,
            "secondary": secondary,
        }
        print(
            f"{name} ({tag}): C3-C1 test EX {100 * primary['point']:+.2f} pp "
            f"[{100 * primary['lo']:+.2f}, {100 * primary['hi']:+.2f}], "
            f"threshold {100 * threshold:.0f} pp -> {outcome}"
        )
    s_vs_m = compare(args.results, c3_runs("qwen05b"), c3_runs("qwen15b"), PRIMARY_METRIC)
    out["secondary_size_c3"] = s_vs_m
    (args.results / "hypotheses.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
