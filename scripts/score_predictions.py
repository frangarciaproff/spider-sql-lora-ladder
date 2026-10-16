"""Score a predictions file with the metrics of its split (SPEC 7.1).

Needs SPIDER_DIR and TESTSUITE_DIR. Reads <pred-dir>/<split>.jsonl and <split>.meta.json, writes
<out-dir>/<split>.summary.json, <split>.jsonl and a copy of the meta file.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from spider_sql.data import DataPaths
from spider_sql.evaluate import align_predictions, score_split, write_scores
from spider_sql.split import load_all_splits


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pred-dir", type=Path, required=True)
    parser.add_argument("--split", choices=("validation", "dev", "test"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--partial", action="store_true", help="smoke runs only, never reported")
    args = parser.parse_args(argv)

    paths = DataPaths.from_env()
    rows_path = args.pred_dir / f"{args.split}.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line]
    examples, preds = align_predictions(
        load_all_splits(paths.spider)[args.split], rows, partial=args.partial
    )
    result = score_split(args.split, examples, preds, paths)
    if args.partial:
        summary = result["summary"]
        assert isinstance(summary, dict)
        summary["partial"] = True
    write_scores(result, args.out_dir, args.split)
    for name in (f"{args.split}.meta.json", "meta.json"):  # meta.json: runs before 2026-10-16
        meta = args.pred_dir / name
        if meta.is_file():
            shutil.copyfile(meta, args.out_dir / name)
            break
    summary = result["summary"]
    assert isinstance(summary, dict)
    for name, value in summary.items():
        if isinstance(value, dict):
            print(
                f"{name:10s} {value['accuracy']:.4f}  "
                f"({value['n_correct']}/{value['n']})  {value['reasons']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
