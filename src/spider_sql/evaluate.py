"""Score predictions on a split with every metric SPEC section 7.1 defines for it."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from spider_sql.data import DataPaths, Example, sqlite_path
from spider_sql.execution import DEFAULT_TIMEOUT_S, GoldCache, exec_match


@dataclass(frozen=True)
class Metric:
    name: str
    databases: str  # "spider" (original file only) or "testsuite" (original + variants)
    keep_distinct: bool


METRICS: dict[str, tuple[Metric, ...]] = {
    "validation": (Metric("ex", "spider", False),),
    "dev": (
        Metric("ex", "spider", False),
        Metric("ts", "testsuite", False),
        Metric("ts_strict", "testsuite", True),
    ),
    "test": (Metric("ex", "spider", False), Metric("ex_strict", "spider", True)),
}


def database_path(paths: DataPaths, metric: Metric, example: Example) -> Path:
    if metric.databases == "testsuite":
        if paths.testsuite is None:
            raise RuntimeError("TESTSUITE_DIR is not set")
        return paths.testsuite / "database" / example.db_id / f"{example.db_id}.sqlite"
    return sqlite_path(paths.spider, example.source, example.db_id)


def score_split(
    split: str,
    examples: Sequence[Example],
    predictions: Sequence[str],
    paths: DataPaths,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, object]:
    """Returns {"summary": {metric: {...}}, "per_example": [...]}. No dataset text is stored."""
    if len(examples) != len(predictions):
        raise ValueError(f"{len(examples)} examples but {len(predictions)} predictions")
    metrics = METRICS[split]
    cache: GoldCache = {}
    per_example: list[dict[str, object]] = []
    for i, (example, pred) in enumerate(zip(examples, predictions, strict=True)):
        row: dict[str, object] = {
            "source": example.source,
            "index": example.index,
            "db_id": example.db_id,
            "pred": pred,
        }
        for metric in metrics:
            result = exec_match(
                database_path(paths, metric, example),
                pred,
                example.query,
                keep_distinct=metric.keep_distinct,
                timeout_s=timeout_s,
                gold_cache=cache,
            )
            row[metric.name] = int(result.correct)
            row[f"{metric.name}_reason"] = result.reason
        per_example.append(row)
        if progress is not None:
            progress(i + 1, len(examples))
    summary: dict[str, object] = {}
    for metric in metrics:
        hits = [int(str(r[metric.name])) for r in per_example]
        reasons = Counter(str(r[f"{metric.name}_reason"]) for r in per_example)
        summary[metric.name] = {
            "accuracy": sum(hits) / len(hits) if hits else float("nan"),
            "n": len(hits),
            "n_correct": sum(hits),
            "reasons": dict(sorted(reasons.items())),
        }
    return {"summary": summary, "per_example": per_example}


def write_scores(result: dict[str, object], out_dir: Path, split: str) -> tuple[Path, Path]:
    """<split>.summary.json (readable) and <split>.jsonl (one compact line per example)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / f"{split}.summary.json"
    rows_path = out_dir / f"{split}.jsonl"
    summary_path.write_text(json.dumps(result["summary"], indent=2) + "\n", encoding="utf-8")
    rows = result["per_example"]
    assert isinstance(rows, list)
    lines = [json.dumps(row, separators=(",", ":"), ensure_ascii=False) for row in rows]
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path, rows_path


def align_predictions(
    examples: Sequence[Example],
    rows: Sequence[dict[str, object]],
    partial: bool = False,
) -> tuple[list[Example], list[str]]:
    """Match prediction rows to examples by key "<source>:<index>". Missing predictions are an
    error unless partial (smoke runs only; partial scores are never reported)."""
    by_key = {str(r["key"]): str(r["pred"]) for r in rows}
    kept: list[Example] = []
    preds: list[str] = []
    missing = 0
    for example in examples:
        pred = by_key.get(f"{example.source}:{example.index}")
        if pred is None:
            missing += 1
            continue
        kept.append(example)
        preds.append(pred)
    if missing and not partial:
        raise ValueError(f"{missing} of {len(examples)} examples have no prediction")
    return kept, preds
