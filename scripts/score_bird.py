"""Score BIRD predictions with the official rule (SPEC 8; see spider_sql.bird).

Needs BIRD_DIR and BIRD_DB_DIR. Reads <pred-dir>/<variant>.jsonl, writes <out-dir>/<variant>.jsonl
(one row per question: ex, ex_reason, difficulty), <variant>.summary.json and the meta file.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from spider_sql.bird import SOURCE, VARIANTS, BirdPaths, bird_match, load_bird, run, summarize
from spider_sql.execution import QueryOutcome


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pred-dir", type=Path, default=None)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="bird_dev")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--gold-check",
        action="store_true",
        help="score gold as prediction; checks data, writes nothing",
    )
    parser.add_argument("--partial", action="store_true", help="smoke runs only, never reported")
    args = parser.parse_args(argv)

    paths = BirdPaths.from_env()
    examples = load_bird(paths.questions)
    if args.gold_check:
        preds = {e.index: e.query for e in examples}
    else:
        if args.pred_dir is None or args.out_dir is None:
            raise SystemExit("--pred-dir and --out-dir are required unless --gold-check")
        path = args.pred_dir / f"{args.variant}.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        preds = {int(r["index"]): str(r["pred"]) for r in map(json.loads, filter(None, lines))}
    if not args.partial and set(preds) != {e.index for e in examples}:
        raise SystemExit(f"{len(preds)} predictions for {len(examples)} questions; use --partial")
    rows = []
    for e in examples:
        if e.index not in preds:
            continue
        db = paths.sqlite(e.db_id)
        pred = preds[e.index]
        pred_out = run(db, pred) if pred.strip() else QueryOutcome(ok=False, error="empty")
        gold_out = run(db, e.query)
        score, reason = bird_match(pred_out, gold_out)
        if args.gold_check and reason != "match":
            print(f"  index {e.index} ({e.db_id}): {reason}: {gold_out.error or pred_out.error}")
        if reason == "pred_error" and not pred.strip():
            reason = "pred_empty"
        rows.append(
            {
                "source": SOURCE,
                "index": e.index,
                "db_id": e.db_id,
                "difficulty": e.difficulty,
                "pred": pred,
                "ex": score,
                "ex_reason": reason,
                **({"gold_error": gold_out.error} if reason == "gold_error" else {}),
            }
        )
    summary = {"variant": args.variant, "partial": args.partial, **summarize(rows)}
    ex = summary["ex"]
    assert isinstance(ex, dict)
    if args.gold_check:
        print(f"gold vs gold: {ex['accuracy']:.4f} ({ex['n_correct']}/{ex['n']}) {ex['reasons']}")
        return 0
    assert args.pred_dir is not None and args.out_dir is not None
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"{args.variant}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    (args.out_dir / f"{args.variant}.summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    meta = args.pred_dir / f"{args.variant}.meta.json"
    if meta.is_file() and meta.resolve() != (args.out_dir / meta.name).resolve():
        shutil.copyfile(meta, args.out_dir / meta.name)
    print(f"{args.variant} ex {ex['accuracy']:.4f} ({ex['n_correct']}/{ex['n']}) {ex['reasons']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
