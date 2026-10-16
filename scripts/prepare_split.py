"""Build the database-level validation split and the leakage report.

Needs SPIDER_DIR. Writes results/split_manifest.json, leakage_report.json and decontamination.json.
Exit code 1 if a db_id is shared or a question+SQL pair still overlaps after cleaning.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from spider_sql.data import DataPaths, load_examples, load_train
from spider_sql.leakage import leakage_report
from spider_sql.split import SPLIT_SEED, VAL_FRACTION, make_split, manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    args = parser.parse_args(argv)

    paths = DataPaths.from_env()
    dev = load_examples(paths.spider, "dev")
    test = load_examples(paths.spider, "test")
    split = make_split(
        load_train(paths.spider),
        fraction=VAL_FRACTION,
        seed=SPLIT_SEED,
        holdouts={"dev": dev, "test": test},
    )
    splits = {"fit": split.fit, "validation": split.validation, "dev": dev, "test": test}
    report = leakage_report(splits)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "split_manifest.json").write_text(
        json.dumps(manifest(split), indent=2) + "\n", encoding="utf-8"
    )
    (args.out_dir / "leakage_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )

    (args.out_dir / "decontamination.json").write_text(
        json.dumps(
            [{"source": e.source, "index": e.index, "db_id": e.db_id} for e in split.removed],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for name, rows in splits.items():
        print(f"{name:11s} examples={len(rows):5d} dbs={len({e.db_id for e in rows})}")
    print("validation dbs:", ", ".join(split.validation_db_ids))
    print("removed from fit (question+SQL pair also in validation/dev/test):", len(split.removed))
    print("shared db_ids:", report["shared_db_ids"] or "none")
    overlaps = report["text_overlaps"]
    assert isinstance(overlaps, dict)
    for name, info in overlaps.items():
        print(
            f"{name:11s} question overlap with fit: {info['n_question_overlap']}, "
            f"question+SQL overlap: {info['n_question_sql_overlap']}"
        )
    pair_left = sum(int(info["n_question_sql_overlap"]) for info in overlaps.values())
    return 1 if report["shared_db_ids"] or pair_left else 0


if __name__ == "__main__":
    raise SystemExit(main())
