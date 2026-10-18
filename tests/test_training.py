import pytest

from spider_sql.data import Example
from spider_sql.training import (
    IGNORE_INDEX,
    TrainConfig,
    encode_examples,
    length_grouping_kwargs,
    mask_labels,
    merge_train_meta,
    run_name,
    split_prompt_completion,
    total_steps,
    warmup_steps,
)


def render(messages: list[dict[str, str]], generation_prompt: bool) -> str:
    """Minimal Qwen-like chat template."""
    text = "".join(f"<s>{m['role']}\n{m['content']}<e>\n" for m in messages)
    return text + ("<s>assistant\n" if generation_prompt else "")


def tokenize(text: str) -> list[int]:
    return [ord(c) for c in text]


def ex(i: int, question: str = "How many?") -> Example:
    return Example("train_spider", i, "d", question, "SELECT count(*) FROM t")


def test_mask_labels_ignores_prompt() -> None:
    row = mask_labels([1, 2, 3], [7, 8])
    assert row["input_ids"] == [1, 2, 3, 7, 8]
    assert row["labels"] == [IGNORE_INDEX] * 3 + [7, 8]
    assert row["attention_mask"] == [1] * 5


def test_completion_is_answer_plus_end_of_turn() -> None:
    messages = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "Q"},
        {"role": "assistant", "content": "SELECT 1"},
    ]
    prompt, completion = split_prompt_completion(render, messages)
    assert prompt.endswith("<s>assistant\n")
    assert completion == "SELECT 1<e>\n"


def test_template_mismatch_raises() -> None:
    def bad(messages: list[dict[str, str]], generation_prompt: bool) -> str:
        return "X" if generation_prompt else "Y"

    with pytest.raises(ValueError):
        split_prompt_completion(
            bad, [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]
        )


def test_encode_drops_over_length_and_reports_keys() -> None:
    examples = [ex(0), ex(1, question="x" * 500)]
    rows, dropped = encode_examples(
        examples, lambda e: "CREATE TABLE t (a int);", render, tokenize, 400
    )
    assert dropped == ["train_spider:1"]
    assert len(rows) == 1
    labels = rows[0]["labels"]
    supervised = "".join(chr(t) for t in labels if t != IGNORE_INDEX)
    assert supervised == "SELECT count(*) FROM t<e>\n"


def test_steps_and_run_name() -> None:
    config = TrainConfig(learning_rate=1e-4, epochs=3, seed=2)
    assert config.effective_batch == 16
    assert total_steps(8106, config) == 507 * 3
    assert warmup_steps(8106, config) == 46
    assert run_name("qwen05b", config) == "qwen05b_c3_lr0.0001_ep3_seed2"


def test_length_grouping_across_transformers_versions() -> None:
    assert length_grouping_kwargs({"group_by_length", "seed"}) == {"group_by_length": True}
    assert length_grouping_kwargs({"train_sampling_strategy"}) == {
        "train_sampling_strategy": "group_by_length"
    }
    with pytest.raises(RuntimeError):
        length_grouping_kwargs({"seed"})


def test_resumed_session_is_appended_not_overwritten() -> None:
    first = merge_train_meta(
        None, {"n_rows": 10}, {"seconds_this_session": 900.0, "peak_vram_gb": 2.3}
    )
    second = merge_train_meta(
        first, {"n_rows": 10}, {"seconds_this_session": 1.0, "peak_vram_gb": 1.1}
    )
    assert len(second["sessions"]) == 2
    assert second["sessions"][0]["seconds_this_session"] == 900.0
    assert second["total_train_seconds"] == 901.0
    assert second["max_peak_vram_gb"] == 2.3
