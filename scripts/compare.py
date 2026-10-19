"""Paired comparison of runs on one split (SPEC 7.2): B minus A, where B may be several seeds.

Writes results/comparisons/<name>.json. Example:
  python scripts/compare.py --split dev --a qwen05b_c1_zero_shot \
    --b qwen05b_c3_lr0.0002_ep2_seed0 qwen05b_c3_lr0.0002_ep2_seed1 qwen05b_c3_lr0.0002_ep2_seed2
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from spider_sql.evaluate import METRICS
from spider_sql.stats import load_rows, mcnemar_exact, paired_cluster_bootstrap, seed_average


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("validation", "dev", "test"), required=True)
    parser.add_argument("--a", nargs="+", required=True, help="baseline run(s)")
    parser.add_argument("--b", nargs="+", required=True, help="compared run(s), e.g. seeds")
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--name", default=None)
    parser.add_argument("--n-boot", type=int, default=10_000)
    args = parser.parse_args(argv)

    def load(runs: list[str]) -> list[dict]:  # type: ignore[type-arg]
        return [load_rows(args.results / run / f"{args.split}.jsonl") for run in runs]

    a_runs, b_runs = load(args.a), load(args.b)
    clusters = {k: str(v["db_id"]) for k, v in a_runs[0].items()}
    out: dict[str, object] = {"split": args.split, "a": args.a, "b": args.b, "metrics": {}}
    metrics = out["metrics"]
    assert isinstance(metrics, dict)
    for metric in (m.name for m in METRICS[args.split]):
        a_avg, b_avg = seed_average(a_runs, metric), seed_average(b_runs, metric)
        boot = paired_cluster_bootstrap(a_avg, b_avg, clusters, n_boot=args.n_boot)
        per_seed = [
            mcnemar_exact(
                {k: int(str(v[metric])) for k, v in a_runs[0].items()},
                {k: int(str(v[metric])) for k, v in b.items()},
            )
            for b in b_runs
        ]
        metrics[metric] = {
            "a_accuracy": sum(a_avg.values()) / len(a_avg),
            "b_accuracy": sum(b_avg.values()) / len(b_avg),
            "difference": boot,
            "mcnemar_per_b_run": per_seed,
        }
        print(
            f"{args.split:10s} {metric:9s} A {100 * metrics[metric]['a_accuracy']:.2f} "
            f"B {100 * metrics[metric]['b_accuracy']:.2f}  B-A {100 * boot['point']:+.1f} pp "
            f"[{100 * boot['lo']:+.1f}, {100 * boot['hi']:+.1f}] ({int(boot['n_clusters'])} dbs)"
        )
    name = args.name or f"{args.split}__{args.b[0]}__vs__{args.a[0]}"
    path = args.results / "comparisons" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
