import json
from pathlib import Path

import pytest

from spider_sql.generation import (
    Backend,
    PromptRecord,
    batches_by_length,
    check_split_allowed,
    generate_all,
    greedy_settings,
    load_done,
)


class OutOfMemoryError(RuntimeError):
    pass


def records(n: int) -> list[PromptRecord]:
    return [
        PromptRecord(f"dev:{i}", "dev", i, "d", [{"role": "user", "content": "x" * (i + 1)}])
        for i in range(n)
    ]


def fake_backend(max_batch: int | None = None, calls: list[int] | None = None) -> Backend:
    def run_batch(texts: list[str]) -> list[tuple[str, int]]:
        if calls is not None:
            calls.append(len(texts))
        if max_batch is not None and len(texts) > max_batch:
            raise OutOfMemoryError("CUDA out of memory")
        return [(f"```sql\nSELECT {len(t)};\n```", 3) for t in texts]

    return Backend(render=lambda m: m[-1]["content"], count_tokens=len, run_batch=run_batch)


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_outputs_stay_aligned_with_records_despite_length_sorting(tmp_path: Path) -> None:
    out = tmp_path / "dev.jsonl"
    generate_all(records(5), fake_backend(), out, batch_size=2, log=lambda s: None)
    rows = {r["key"]: r for r in read(out)}
    assert len(rows) == 5
    for i in range(5):
        assert rows[f"dev:{i}"]["pred"] == f"SELECT {i + 1}"
        assert rows[f"dev:{i}"]["prompt_tokens"] == i + 1


def test_resume_skips_done_and_drops_truncated_line(tmp_path: Path) -> None:
    out = tmp_path / "dev.jsonl"
    done = {"key": "dev:0", "source": "dev", "index": 0, "db_id": "d", "raw": "", "pred": "X"}
    out.write_text(json.dumps(done) + "\n" + '{"key": "dev:1", "trunc')
    calls: list[int] = []
    stats = generate_all(
        records(3), fake_backend(calls=calls), out, batch_size=8, log=lambda s: None
    )
    rows = read(out)
    assert stats["n_generated"] == 2
    assert sum(calls) == 2
    assert sorted(r["key"] for r in rows) == ["dev:0", "dev:1", "dev:2"]
    assert next(r for r in rows if r["key"] == "dev:0")["pred"] == "X"


def test_out_of_memory_halves_the_batch(tmp_path: Path) -> None:
    out = tmp_path / "dev.jsonl"
    calls: list[int] = []
    ooms: list[int] = []
    generate_all(
        records(8),
        fake_backend(max_batch=2, calls=calls),
        out,
        batch_size=8,
        log=lambda s: None,
        on_oom=ooms.append,
    )
    assert len(read(out)) == 8
    assert ooms[0] == 8
    assert max(c for c in calls if c not in ooms) <= 2


def test_non_oom_errors_propagate(tmp_path: Path) -> None:
    def broken(texts: list[str]) -> list[tuple[str, int]]:
        raise ValueError("boom")

    backend = Backend(render=lambda m: "x", count_tokens=len, run_batch=broken)
    with pytest.raises(ValueError):
        generate_all(records(2), backend, tmp_path / "o.jsonl", 2, log=lambda s: None)


def test_batches_longest_first() -> None:
    assert batches_by_length([1, 5, 3, 5], 2) == [[1, 3], [2, 0]]


def test_load_done_missing_file(tmp_path: Path) -> None:
    assert load_done(tmp_path / "none.jsonl") == {}


def test_greedy_settings_override_sampling() -> None:
    settings = greedy_settings(256)
    assert settings["do_sample"] is False
    assert settings["repetition_penalty"] == 1.0
    assert settings["temperature"] is None


def test_test_split_needs_final_flag() -> None:
    with pytest.raises(SystemExit):
        check_split_allowed("test", final=False)
    check_split_allowed("test", final=True)
    check_split_allowed("dev", final=False)
