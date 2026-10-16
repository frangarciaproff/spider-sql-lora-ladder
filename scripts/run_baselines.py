"""Score the trivial baselines B0a and B0b on validation, dev and test.

Needs SPIDER_DIR and TESTSUITE_DIR. Writes results/baselines/<baseline>/<split>.summary.json
and <split>.jsonl (per-example correctness).
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from spider_sql.baselines import first_table, overlap_count
from spider_sql.data import DataPaths, Example, load_examples, load_train, sqlite_path
from spider_sql.evaluate import score_split, write_scores
from spider_sql.schema import table_names
from spider_sql.split import make_split

BASELINES: dict[str, Callable[[Example, list[str]], str]] = {
    "b0a_first_table": lambda ex, tables: first_table(tables),
    "b0b_overlap_count": lambda ex, tables: overlap_count(ex.question, tables),
}


def load_splits(paths: DataPaths) -> dict[str, list[Example]]:
    dev = load_examples(paths.spider, "dev")
    test = load_examples(paths.spider, "test")
    split = make_split(load_train(paths.spider), holdouts={"dev": dev, "test": test})
    return {"validation": list(split.validation), "dev": dev, "test": test}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("results/baselines"))
    parser.add_argument("--splits", nargs="+", default=["validation", "dev", "test"])
    parser.add_argument("--limit", type=int, default=None, help="first N examples (smoke test)")
    args = parser.parse_args(argv)

    paths = DataPaths.from_env()
    splits = load_splits(paths)
    for split_name in args.splits:
        examples = splits[split_name][: args.limit]
        for name, make_pred in BASELINES.items():
            start = time.monotonic()
            preds = [
                make_pred(ex, table_names(sqlite_path(paths.spider, ex.source, ex.db_id)))
                for ex in examples
            ]
            result = score_split(split_name, examples, preds, paths)
            write_scores(result, args.out_dir / name, split_name)
            summary = result["summary"]
            assert isinstance(summary, dict)
            scores = ", ".join(f"{m}={v['accuracy']:.4f}" for m, v in summary.items())
            print(
                f"{split_name:10s} {name:18s} n={len(examples):5d} {scores} "
                f"({time.monotonic() - start:.0f}s)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
