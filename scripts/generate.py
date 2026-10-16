"""Generate SQL for one split with one condition (C1 zero-shot, C2 three-shot, C3 adapter).

Needs SPIDER_DIR. Writes <out-dir>/<split>.jsonl (resumable) and <out-dir>/meta.json.
The test split needs --final: SPEC 3.2 allows one test run per condition, after freezing.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from spider_sql.data import DataPaths, Example, sqlite_path
from spider_sql.generation import (
    PromptRecord,
    check_split_allowed,
    environment_info,
    example_key,
    generate_all,
    greedy_settings,
    hf_backend,
    load_hf,
)
from spider_sql.prompt import SYSTEM_PROMPT, Shot, build_messages, select_shots
from spider_sql.schema import schema_ddl
from spider_sql.split import load_all_splits

CONDITIONS = ("zero_shot", "three_shot", "adapter")


def schema_for(paths: DataPaths, example: Example) -> str:
    return schema_ddl(sqlite_path(paths.spider, example.source, example.db_id))


def build_records(
    paths: DataPaths, examples: Sequence[Example], shots: Sequence[Shot]
) -> list[PromptRecord]:
    return [
        PromptRecord(
            key=example_key(ex.source, ex.index),
            source=ex.source,
            index=ex.index,
            db_id=ex.db_id,
            messages=build_messages(schema_for(paths, ex), ex.question, shots),
        )
        for ex in examples
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-0.5B-Instruct")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--condition", choices=CONDITIONS, required=True)
    parser.add_argument("--adapter", default=None, help="LoRA adapter folder (condition adapter)")
    parser.add_argument("--split", choices=("validation", "dev", "test"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--limit", type=int, default=None, help="first N examples (smoke test)")
    parser.add_argument("--final", action="store_true", help="required for the test split")
    args = parser.parse_args(argv)

    check_split_allowed(args.split, args.final)
    if (args.condition == "adapter") != (args.adapter is not None):
        raise SystemExit("--adapter is required with condition adapter, and only then")

    paths = DataPaths.from_env()
    splits = load_all_splits(paths.spider)
    examples = splits[args.split][: args.limit]
    shots: list[Shot] = []
    if args.condition == "three_shot":
        chosen = select_shots(splits["fit"], lambda e: schema_for(paths, e))
        shots = [Shot(schema_for(paths, e), e.question, e.query) for e in chosen]
        shot_keys = [example_key(e.source, e.index) for e in chosen]
    else:
        shot_keys = []
    records = build_records(paths, examples, shots)

    tokenizer, model = load_hf(args.model, args.revision, args.adapter, args.dtype)
    backend = hf_backend(tokenizer, model, args.max_new_tokens)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    meta_path = args.out_dir / "meta.json"
    meta = {
        "split": args.split,
        "condition": args.condition,
        "adapter": args.adapter,
        "n_examples": len(examples),
        "limit": args.limit,
        "batch_size": args.batch_size,
        "dtype": args.dtype,
        "decoding": greedy_settings(args.max_new_tokens),
        "system_prompt": SYSTEM_PROMPT,
        "shot_keys": shot_keys,
        "started_utc": datetime.now(UTC).isoformat(),
        "environment": environment_info(model, args.model, args.revision),
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    stats = generate_all(records, backend, args.out_dir / f"{args.split}.jsonl", args.batch_size)
    meta["finished_utc"] = datetime.now(UTC).isoformat()
    meta["last_session_stats"] = stats
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    seconds = stats["seconds"] or 1.0
    print(
        f"done: {int(stats['n_generated'])} prompts in {seconds:.0f}s, "
        f"{stats['new_tokens'] / seconds:.0f} new tokens/s, "
        f"max prompt {int(stats['max_prompt_tokens'])} tokens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
