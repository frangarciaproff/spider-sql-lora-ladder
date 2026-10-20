"""Execution-based comparison of a predicted SQL query with the gold query.

Semantics follow taoyds/test-suite-sql-eval (see _vendor): bag semantics, row order ignored
unless the gold query contains ORDER BY, column order ignored, DISTINCT removed from both
queries unless keep_distinct. The query is run on every .sqlite file in the folder of
db_path (the original plus test-suite variants, if present); it must match on all of them.

Differences from the upstream script, all intended:
- the timeout is enforced (upstream's asyncio timeout cannot interrupt a running query);
- databases are opened read-only (upstream could be modified by INSERT/DELETE predictions);
- results are capped at MAX_ROWS rows;
- an empty or unparsable prediction counts as wrong instead of crashing.

Inherited quirk: with keep_distinct False, upstream's remove_distinct re-tokenizes only the
first SQL statement, so any statement after the first is silently dropped. With keep_distinct
True a second statement is an execution error. The pipeline extracts the first statement
before calling exec_match, so this does not affect model predictions.
"""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from spider_sql._vendor.test_suite_eval import (
    postprocess,
    remove_distinct,
    replace_cur_year,
    result_eq,
)

DEFAULT_TIMEOUT_S = 60.0
MAX_ROWS = 1_000_000
PROGRESS_STEPS = 10_000

Row = tuple[object, ...]


def _remove_distinct(sql: str) -> str:
    return str(remove_distinct(sql))  # type: ignore[no-untyped-call]


class GoldExecutionError(RuntimeError):
    """The gold query failed. This is a setup error, never a model error."""


@dataclass(frozen=True)
class QueryOutcome:
    ok: bool
    rows: tuple[Row, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class MatchResult:
    """reason: match, mismatch, pred_empty, pred_unparsable, pred_error, pred_timeout,
    pred_too_many_rows."""

    correct: bool
    reason: str


GoldCache = dict[tuple[str, str], QueryOutcome]


def execute(
    sqlite_path: Path,
    query: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_rows: int = MAX_ROWS,
    lenient_text: bool = True,
) -> QueryOutcome:
    """Run one query read-only. Errors, timeouts and oversized results are returned, not raised.

    lenient_text drops undecodable bytes (as the Spider test-suite script does); False keeps
    sqlite3's default, where invalid UTF-8 is an error (as the BIRD script does)."""
    deadline = time.monotonic() + timeout_s
    uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        return QueryOutcome(ok=False, error=f"connect: {exc}")
    try:
        if lenient_text:
            connection.text_factory = lambda raw: raw.decode(errors="ignore")
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), PROGRESS_STEPS)
        cursor = connection.cursor()
        cursor.execute(replace_cur_year(query))
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            return QueryOutcome(ok=False, error="too_many_rows")
        return QueryOutcome(ok=True, rows=tuple(rows))
    except sqlite3.Error as exc:
        text = str(exc)
        return QueryOutcome(ok=False, error="timeout" if "interrupted" in text else text)
    finally:
        connection.close()


def database_files(db_path: Path) -> list[Path]:
    """db_path first, then the other .sqlite files in its folder, sorted."""
    if not db_path.is_file():
        raise FileNotFoundError(f"missing database: {db_path}")
    others = sorted(p for p in db_path.parent.glob("*.sqlite") if p != db_path)
    return [db_path, *others]


def _same(gold_rows: tuple[Row, ...], pred_rows: tuple[Row, ...], order_matters: bool) -> bool:
    # Identity column order is one of the permutations result_eq tries; checking it first
    # gives the same answer and avoids a huge permutation search for wide results.
    if order_matters:
        if gold_rows == pred_rows:
            return True
    elif Counter(gold_rows) == Counter(pred_rows):
        return True
    return bool(result_eq(list(gold_rows), list(pred_rows), order_matters))


def _failure_reason(error: str) -> str:
    if error == "timeout":
        return "pred_timeout"
    if error == "too_many_rows":
        return "pred_too_many_rows"
    return "pred_error"


def exec_match(
    db_path: Path,
    pred: str,
    gold: str,
    keep_distinct: bool = False,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    gold_cache: GoldCache | None = None,
) -> MatchResult:
    if not pred.strip():
        return MatchResult(correct=False, reason="pred_empty")
    p_str, g_str = postprocess(pred), postprocess(gold)
    if not keep_distinct:
        try:
            p_str = _remove_distinct(p_str)
        except Exception:
            return MatchResult(correct=False, reason="pred_unparsable")
        g_str = _remove_distinct(g_str)
    order_matters = "order by" in g_str.lower()

    for path in database_files(db_path):
        key = (str(path), g_str)
        gold_out = gold_cache.get(key) if gold_cache is not None else None
        if gold_out is None:
            gold_out = execute(path, g_str, timeout_s=timeout_s)
            if gold_cache is not None:
                gold_cache[key] = gold_out
        if not gold_out.ok:
            raise GoldExecutionError(f"gold failed on {path}: {gold_out.error}\n{g_str}")
        pred_out = execute(path, p_str, timeout_s=timeout_s)
        if not pred_out.ok:
            return MatchResult(correct=False, reason=_failure_reason(pred_out.error))
        if not _same(gold_out.rows, pred_out.rows, order_matters):
            return MatchResult(correct=False, reason="mismatch")
    return MatchResult(correct=True, reason="match")
