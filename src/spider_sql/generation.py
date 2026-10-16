"""Batched greedy generation with resume after a crash or a Colab disconnect.

The orchestration (resume, length-sorted batching, out-of-memory halving) is plain Python and
unit-tested. The Hugging Face backend imports torch and transformers lazily, so CI does not
need them.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spider_sql.prompt import Message, extract_sql


@dataclass(frozen=True)
class PromptRecord:
    key: str
    source: str
    index: int
    db_id: str
    messages: list[Message]


@dataclass(frozen=True)
class Backend:
    render: Callable[[list[Message]], str]
    count_tokens: Callable[[str], int]
    run_batch: Callable[[list[str]], list[tuple[str, int]]]  # (decoded text, new tokens)


def check_split_allowed(split: str, final: bool) -> None:
    """SPEC 3.2: test is run once per condition, after freezing; it needs an explicit flag."""
    if split == "test" and not final:
        raise SystemExit("refusing to generate on test without --final (SPEC 3.2)")


def example_key(source: str, index: int) -> str:
    return f"{source}:{index}"


def load_done(path: Path) -> dict[str, dict[str, Any]]:
    """Valid rows already written. A truncated last line from a crash is dropped."""
    if not path.is_file():
        return {}
    done: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        done[str(row["key"])] = row
    return done


def batches_by_length(lengths: Sequence[int], batch_size: int) -> list[list[int]]:
    """Longest first, so an out-of-memory error shows up in the first batch."""
    order = sorted(range(len(lengths)), key=lambda i: (-lengths[i], i))
    return [order[i : i + batch_size] for i in range(0, len(order), batch_size)]


def is_oom(exc: BaseException) -> bool:
    return type(exc).__name__ == "OutOfMemoryError" or "out of memory" in str(exc).lower()


def _run_with_halving(
    run_batch: Callable[[list[str]], list[tuple[str, int]]],
    texts: list[str],
    on_oom: Callable[[int], None],
) -> list[tuple[str, int]]:
    try:
        return run_batch(texts)
    except Exception as exc:
        if not is_oom(exc) or len(texts) == 1:
            raise
        on_oom(len(texts))
        half = len(texts) // 2
        return _run_with_halving(run_batch, texts[:half], on_oom) + _run_with_halving(
            run_batch, texts[half:], on_oom
        )


def generate_all(
    records: Sequence[PromptRecord],
    backend: Backend,
    out_path: Path,
    batch_size: int,
    log: Callable[[str], None] = print,
    on_oom: Callable[[int], None] | None = None,
) -> dict[str, float]:
    """Append one JSON line per record to out_path, skipping records already done."""
    done = load_done(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in done.values()),
        encoding="utf-8",
    )
    todo = [r for r in records if r.key not in done]
    log(f"{len(done)} already done, {len(todo)} to generate")
    texts = [backend.render(r.messages) for r in todo]
    lengths = [backend.count_tokens(t) for t in texts]
    oom_handler = on_oom or (lambda n: log(f"out of memory at batch {n}, halving"))

    start = time.monotonic()
    new_tokens_total = 0
    finished = 0
    with out_path.open("a", encoding="utf-8") as handle:
        for batch in batches_by_length(lengths, batch_size):
            outputs = _run_with_halving(backend.run_batch, [texts[i] for i in batch], oom_handler)
            for i, (raw, n_new) in zip(batch, outputs, strict=True):
                record = todo[i]
                row = {
                    "key": record.key,
                    "source": record.source,
                    "index": record.index,
                    "db_id": record.db_id,
                    "raw": raw,
                    "pred": extract_sql(raw),
                    "prompt_tokens": lengths[i],
                    "new_tokens": n_new,
                }
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                new_tokens_total += n_new
            handle.flush()
            finished += len(batch)
            log(f"{finished}/{len(todo)}")
    elapsed = time.monotonic() - start
    return {
        "n_generated": float(len(todo)),
        "seconds": elapsed,
        "new_tokens": float(new_tokens_total),
        "max_prompt_tokens": float(max(lengths, default=0)),
    }


def greedy_settings(max_new_tokens: int) -> dict[str, object]:
    """SPEC 5: greedy, one beam, no repetition penalty; overrides the model's sampling defaults."""
    return {
        "do_sample": False,
        "num_beams": 1,
        "temperature": None,
        "top_p": None,
        "top_k": None,
        "repetition_penalty": 1.0,
        "max_new_tokens": max_new_tokens,
    }


def load_hf(
    model_id: str,
    revision: str,
    adapter: str | None,
    dtype: str,
) -> tuple[Any, Any]:
    """Tokenizer (left padding) and model in eval mode on the GPU; LoRA adapter merged if given."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    torch_dtype = getattr(torch, dtype)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, dtype=torch_dtype, device_map="cuda"
        )
    except TypeError:  # transformers < 4.56 uses torch_dtype
        model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, torch_dtype=torch_dtype, device_map="cuda"
        )
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    model.eval()
    return tokenizer, model


def hf_backend(tokenizer: Any, model: Any, max_new_tokens: int) -> Backend:
    import copy

    import torch

    config = copy.deepcopy(model.generation_config)
    for name, value in greedy_settings(max_new_tokens).items():
        setattr(config, name, value)
    config.pad_token_id = tokenizer.pad_token_id

    def render(messages: list[Message]) -> str:
        return str(
            tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        )

    def count_tokens(text: str) -> int:
        return len(tokenizer(text, add_special_tokens=False).input_ids)

    def run_batch(texts: list[str]) -> list[tuple[str, int]]:
        encoded = tokenizer(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(
            model.device
        )
        with torch.inference_mode():
            output = model.generate(**encoded, generation_config=config)
        new = output[:, encoded.input_ids.shape[1] :]
        decoded = tokenizer.batch_decode(new, skip_special_tokens=True)
        counts = (new != tokenizer.pad_token_id).sum(dim=1).tolist()
        return list(zip(decoded, (int(c) for c in counts), strict=True))

    return Backend(render=render, count_tokens=count_tokens, run_batch=run_batch)


def environment_info(model: Any, model_id: str, revision: str) -> dict[str, object]:
    """Versions, GPU and the resolved model commit, for results/ traceability."""
    import platform

    import torch
    import transformers

    info: dict[str, object] = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "model_id": model_id,
        "revision_requested": revision,
        "model_generation_config_defaults": model.generation_config.to_dict(),
    }
    try:
        from huggingface_hub import model_info

        info["revision_resolved"] = model_info(model_id, revision=revision).sha
    except Exception as exc:  # offline or API change: record why
        info["revision_resolved"] = f"unavailable: {exc}"
    try:
        import peft

        info["peft"] = peft.__version__
    except ImportError:
        info["peft"] = None
    return info
