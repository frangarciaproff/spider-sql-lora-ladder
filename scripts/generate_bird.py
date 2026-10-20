"""Generate SQL for BIRD dev (SPEC 8) with C1 (zero-shot) or C3 (adapter). No training on BIRD.

Needs BIRD_DIR and BIRD_DB_DIR. Writes <out-dir>/<variant>.jsonl (resumable) and
<variant>.meta.json; variant bird_dev has the evidence in the prompt, bird_dev_noev does not.
Same template, system prompt and greedy decoding as Spider; max_new_tokens is 512 because
BIRD gold queries are longer (docs/DECISIONS.md, 2026-10-20).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from spider_sql.bird import SOURCE, VARIANTS, BirdPaths, load_bird, question_text
from spider_sql.bundle import sha256_file
from spider_sql.generation import (
    PromptRecord,
    environment_info,
    example_key,
    generate_all,
    greedy_settings,
    hf_backend,
    load_hf,
)
from spider_sql.prompt import SYSTEM_PROMPT, build_messages
from spider_sql.schema import schema_ddl

MAX_NEW_TOKENS = 512


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--adapter", default=None, help="LoRA adapter folder; omit for C1")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="bird_dev")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--limit", type=int, default=None, help="first N questions (smoke test)")
    args = parser.parse_args(argv)

    paths = BirdPaths.from_env()
    examples = load_bird(paths.questions)[: args.limit]
    with_evidence = VARIANTS[args.variant]
    records = [
        PromptRecord(
            key=example_key(SOURCE, e.index),
            source=SOURCE,
            index=e.index,
            db_id=e.db_id,
            messages=build_messages(
                schema_ddl(paths.sqlite(e.db_id)), question_text(e, with_evidence)
            ),
        )
        for e in examples
    ]
    tokenizer, model = load_hf(args.model, args.revision, args.adapter, args.dtype)
    backend = hf_backend(tokenizer, model, MAX_NEW_TOKENS)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    weights = Path(args.adapter) / "adapter_model.safetensors" if args.adapter else None
    meta_path = args.out_dir / f"{args.variant}.meta.json"
    meta: dict[str, object] = {
        "split": args.variant,
        "condition": "adapter" if args.adapter else "zero_shot",
        "with_evidence": with_evidence,
        "adapter": args.adapter,
        "adapter_sha256": sha256_file(weights) if weights and weights.is_file() else None,
        "questions_sha256": sha256_file(paths.questions),
        "n_examples": len(examples),
        "limit": args.limit,
        "batch_size": args.batch_size,
        "dtype": args.dtype,
        "decoding": greedy_settings(MAX_NEW_TOKENS),
        "system_prompt": SYSTEM_PROMPT,
        "started_utc": datetime.now(UTC).isoformat(),
        "environment": environment_info(model, args.model, args.revision),
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8")
    stats = generate_all(records, backend, args.out_dir / f"{args.variant}.jsonl", args.batch_size)
    meta["finished_utc"] = datetime.now(UTC).isoformat()
    meta["last_session_stats"] = stats
    meta_path.write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        f"done: {int(stats['n_generated'])} prompts in {stats['seconds']:.0f}s, "
        f"max prompt {int(stats['max_prompt_tokens'])} tokens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
