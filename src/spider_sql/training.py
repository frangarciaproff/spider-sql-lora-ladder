"""LoRA fine-tuning (C3): data encoding with completion-only labels, and the training run.

Encoding is plain Python and unit-tested. Model code imports torch, transformers, peft and
(optionally) unsloth lazily, so CI does not need them.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from spider_sql.data import Example
from spider_sql.prompt import Message, training_messages

IGNORE_INDEX = -100
LORA_TARGETS = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


@dataclass(frozen=True)
class TrainConfig:
    """SPEC 6. Defaults are the frozen starting point; lr and epochs are the tuning grid."""

    model_id: str = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
    revision: str = "main"
    seed: int = 0
    learning_rate: float = 2e-4
    epochs: int = 2
    per_device_batch: int = 8
    grad_accum: int = 2
    max_seq_length: int = 2048
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    warmup_fraction: float = 0.03
    backend: str = "unsloth"  # or "peft"

    @property
    def effective_batch(self) -> int:
        return self.per_device_batch * self.grad_accum


def run_name(tag: str, config: TrainConfig) -> str:
    return f"{tag}_c3_lr{config.learning_rate:g}_ep{config.epochs}_seed{config.seed}"


def mask_labels(prompt_ids: Sequence[int], completion_ids: Sequence[int]) -> dict[str, list[int]]:
    """Loss on the completion only: prompt positions get IGNORE_INDEX."""
    input_ids = [*prompt_ids, *completion_ids]
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": [IGNORE_INDEX] * len(prompt_ids) + list(completion_ids),
    }


def split_prompt_completion(
    render: Callable[[list[Message], bool], str], messages: list[Message]
) -> tuple[str, str]:
    """Render with the chat template; the completion is the gold answer plus end-of-turn
    markup. The prompt is exactly what inference sees (add_generation_prompt=True)."""
    prompt = render(messages[:-1], True)
    full = render(messages, False)
    if not full.startswith(prompt):
        raise ValueError("chat template does not extend the generation prompt")
    return prompt, full[len(prompt) :]


def encode_examples(
    examples: Sequence[Example],
    schema_of: Callable[[Example], str],
    render: Callable[[list[Message], bool], str],
    tokenize: Callable[[str], list[int]],
    max_seq_length: int,
) -> tuple[list[dict[str, list[int]]], list[str]]:
    """Encoded rows and the keys of examples dropped for exceeding max_seq_length.
    Prompt and completion are tokenized separately, as generation sees them."""
    rows: list[dict[str, list[int]]] = []
    dropped: list[str] = []
    for ex in examples:
        messages = training_messages(schema_of(ex), ex.question, ex.query)
        prompt, completion = split_prompt_completion(render, messages)
        row = mask_labels(tokenize(prompt), tokenize(completion))
        if len(row["input_ids"]) > max_seq_length:
            dropped.append(f"{ex.source}:{ex.index}")
            continue
        rows.append(row)
    return rows, dropped


def total_steps(n_rows: int, config: TrainConfig) -> int:
    return math.ceil(n_rows / config.effective_batch) * config.epochs


def warmup_steps(n_rows: int, config: TrainConfig) -> int:
    return math.ceil(config.warmup_fraction * total_steps(n_rows, config))


def length_grouping_kwargs(accepted: set[str]) -> dict[str, object]:
    """Length-grouped batching across transformers versions: v4 has group_by_length=True,
    v5 has train_sampling_strategy="group_by_length". Raises if neither exists."""
    if "group_by_length" in accepted:
        return {"group_by_length": True}
    if "train_sampling_strategy" in accepted:
        return {"train_sampling_strategy": "group_by_length"}
    raise RuntimeError("this transformers version has no length-grouped sampling option")


def load_for_training(config: TrainConfig) -> tuple[Any, Any]:
    """fp16 base model with LoRA adapters (fp32) attached. No 4-bit quantization (SPEC 6)."""
    if config.backend == "unsloth":
        import torch
        import unsloth  # noqa: F401  # must be imported before transformers
        from unsloth import FastLanguageModel

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=config.model_id,
            max_seq_length=config.max_seq_length,
            dtype=torch.float16,
            load_in_4bit=False,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=config.lora_r,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            target_modules=list(LORA_TARGETS),
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=config.seed,
        )
        return tokenizer, model

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(config.model_id, revision=config.revision)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            config.model_id, revision=config.revision, dtype=torch.float16
        )
    except TypeError:  # transformers < 4.56
        model = AutoModelForCausalLM.from_pretrained(
            config.model_id, revision=config.revision, torch_dtype=torch.float16
        )
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    lora = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=list(LORA_TARGETS),
        bias="none",
        task_type="CAUSAL_LM",
    )
    return tokenizer, get_peft_model(model, lora)


def train(
    config: TrainConfig,
    rows: list[dict[str, list[int]]],
    tokenizer: Any,
    model: Any,
    out_dir: Path,
    save_steps: int = 100,
    max_steps: int | None = None,
) -> dict[str, object]:
    """Train, resuming from the newest checkpoint in out_dir if one exists. Saves the adapter
    to out_dir/adapter and returns run statistics."""
    import inspect

    import torch
    from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments, set_seed

    set_seed(config.seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    args = TrainingArguments(
        output_dir=str(out_dir),
        seed=config.seed,
        data_seed=config.seed,
        learning_rate=config.learning_rate,
        num_train_epochs=config.epochs,
        max_steps=max_steps if max_steps is not None else -1,
        per_device_train_batch_size=config.per_device_batch,
        gradient_accumulation_steps=config.grad_accum,
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps(len(rows), config),
        optim="adamw_torch",
        weight_decay=0.0,
        fp16=True,
        logging_steps=10,
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=2,
        remove_unused_columns=False,
        report_to="none",
        dataloader_num_workers=2,
        **length_grouping_kwargs(set(inspect.signature(TrainingArguments.__init__).parameters)),
    )
    collator = DataCollatorForSeq2Seq(
        tokenizer, padding=True, label_pad_token_id=IGNORE_INDEX, pad_to_multiple_of=8
    )
    trainer = Trainer(model=model, args=args, train_dataset=rows, data_collator=collator)
    resume = any(out_dir.glob("checkpoint-*"))
    torch.cuda.reset_peak_memory_stats()
    start = time.monotonic()
    result = trainer.train(resume_from_checkpoint=True if resume else None)
    seconds = time.monotonic() - start
    model.save_pretrained(str(out_dir / "adapter"))
    tokenizer.save_pretrained(str(out_dir / "adapter"))
    (out_dir / "log_history.json").write_text(
        json.dumps(trainer.state.log_history, indent=1) + "\n", encoding="utf-8"
    )
    return {
        "resumed": resume,
        "seconds_this_session": seconds,
        "global_step": trainer.state.global_step,
        "train_loss": result.training_loss,
        "peak_vram_gb": torch.cuda.max_memory_allocated() / 1e9,
        "config": asdict(config),
    }


def merge_train_meta(
    existing: dict[str, object] | None,
    static: dict[str, object],
    session: dict[str, object],
) -> dict[str, object]:
    """Keep every training session: a resumed run appends instead of overwriting the stats of
    the session that did the work."""
    meta: dict[str, object] = dict(existing or {})
    sessions = list(meta.get("sessions", []))  # type: ignore[call-overload]
    sessions.append(session)
    meta.update(static)
    meta["sessions"] = sessions
    meta["total_train_seconds"] = sum(float(s.get("seconds_this_session", 0.0)) for s in sessions)
    meta["max_peak_vram_gb"] = max(float(s.get("peak_vram_gb", 0.0)) for s in sessions)
    return meta
