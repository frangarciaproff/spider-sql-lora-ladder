"""Train one LoRA adapter (C3) on the fit split.

Needs SPIDER_DIR. Writes <out-dir>/adapter/, checkpoints, log_history.json and train_meta.json.
Rerunning the same command resumes from the newest checkpoint.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from spider_sql.data import DataPaths, Example, sqlite_path
from spider_sql.prompt import Message
from spider_sql.schema import schema_ddl
from spider_sql.split import load_all_splits
from spider_sql.training import TrainConfig, encode_examples, merge_train_meta, total_steps


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=TrainConfig.model_id)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--per-device-batch", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=2)
    parser.add_argument("--backend", choices=("unsloth", "peft"), default="unsloth")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--max-steps", type=int, default=None, help="smoke test only")
    parser.add_argument("--limit", type=int, default=None, help="first N fit examples (smoke)")
    args = parser.parse_args(argv)

    config = TrainConfig(
        model_id=args.model,
        revision=args.revision,
        seed=args.seed,
        learning_rate=args.lr,
        epochs=args.epochs,
        per_device_batch=args.per_device_batch,
        grad_accum=args.grad_accum,
        backend=args.backend,
    )
    if config.effective_batch != 16:
        print(f"warning: effective batch {config.effective_batch}, SPEC 6 fixes 16")

    from spider_sql.training import load_for_training, train  # heavy imports start here

    tokenizer, model = load_for_training(config)
    paths = DataPaths.from_env()
    fit = load_all_splits(paths.spider)["fit"][: args.limit]

    def schema_of(ex: Example) -> str:
        return schema_ddl(sqlite_path(paths.spider, ex.source, ex.db_id))

    def render(messages: list[Message], generation_prompt: bool) -> str:
        return str(
            tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=generation_prompt
            )
        )

    def tokenize(text: str) -> list[int]:
        return list(tokenizer(text, add_special_tokens=False).input_ids)

    rows, dropped = encode_examples(fit, schema_of, render, tokenize, config.max_seq_length)
    lengths = sorted(len(r["input_ids"]) for r in rows)
    print(
        f"{len(rows)} training rows, {len(dropped)} dropped (> {config.max_seq_length} tokens), "
        f"median {lengths[len(lengths) // 2]} max {lengths[-1]} tokens, "
        f"{total_steps(len(rows), config)} optimizer steps"
    )
    stats = train(config, rows, tokenizer, model, args.out_dir, args.save_steps, args.max_steps)
    meta_path = args.out_dir / "train_meta.json"
    existing = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
    static = {
        "n_rows": len(rows),
        "dropped_keys": dropped,
        "token_length_median": lengths[len(lengths) // 2],
        "token_length_max": lengths[-1],
        "limit": args.limit,
        "max_steps": args.max_steps,
        "config": stats["config"],
    }
    session = {k: v for k, v in stats.items() if k != "config"}
    session["finished_utc"] = datetime.now(UTC).isoformat()
    meta = merge_train_meta(existing, static, session)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(
        f"done: step {stats['global_step']}, loss {stats['train_loss']:.4f}, "
        f"{stats['seconds_this_session']:.0f}s, peak VRAM {stats['peak_vram_gb']:.1f} GB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
