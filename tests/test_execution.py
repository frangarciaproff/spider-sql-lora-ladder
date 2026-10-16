import random
import sqlite3
import time
from pathlib import Path

import pytest

from spider_sql._vendor.test_suite_eval import result_eq
from spider_sql.execution import (
    GoldExecutionError,
    _same,
    database_files,
    exec_match,
    execute,
)


def make_db(path: Path, rows: list[tuple[str, int]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("create table singer (name text, age int)")
    con.executemany("insert into singer values (?, ?)", rows)
    con.commit()
    con.close()
    return path


ROWS = [("ann", 20), ("bob", 25), ("cy", 25), ("di", 40)]


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return make_db(tmp_path / "d" / "d.sqlite", ROWS)


def test_identical_queries_match(db: Path) -> None:
    result = exec_match(db, "SELECT name FROM singer", "SELECT name FROM singer")
    assert (result.correct, result.reason) == (True, "match")


def test_column_order_is_ignored(db: Path) -> None:
    assert exec_match(db, "SELECT age, name FROM singer", "SELECT name, age FROM singer").correct


def test_row_order_ignored_without_order_by(db: Path) -> None:
    pred = "SELECT name FROM singer ORDER BY name DESC"
    assert exec_match(db, pred, "SELECT name FROM singer").correct


def test_row_order_matters_when_gold_has_order_by(db: Path) -> None:
    gold = "SELECT name FROM singer ORDER BY age"
    result = exec_match(db, "SELECT name FROM singer ORDER BY age DESC", gold)
    assert (result.correct, result.reason) == (False, "mismatch")


def test_distinct_removed_unless_keep_distinct(db: Path) -> None:
    gold, pred = "SELECT DISTINCT age FROM singer", "SELECT age FROM singer"
    assert exec_match(db, pred, gold).correct
    assert not exec_match(db, pred, gold, keep_distinct=True).correct


def test_wrong_result_is_mismatch(db: Path) -> None:
    result = exec_match(db, "SELECT name FROM singer WHERE age > 30", "SELECT name FROM singer")
    assert (result.correct, result.reason) == (False, "mismatch")


def test_variants_catch_what_one_database_misses(tmp_path: Path) -> None:
    gold = "SELECT count(*) FROM singer WHERE age > 30"
    pred = "SELECT count(*) FROM singer WHERE age >= 30"
    original = make_db(tmp_path / "a" / "a.sqlite", [("x", 20), ("y", 40)])
    assert exec_match(original, pred, gold).correct  # plain EX false positive
    make_db(tmp_path / "a" / "a_variant.sqlite", [("x", 30), ("y", 40)])
    result = exec_match(original, pred, gold)  # now evaluated on the variant too
    assert (result.correct, result.reason) == (False, "mismatch")
    assert [p.name for p in database_files(original)] == ["a.sqlite", "a_variant.sqlite"]


@pytest.mark.parametrize("pred", ["", "   \n"])
def test_empty_prediction(db: Path, pred: str) -> None:
    assert exec_match(db, pred, "SELECT 1").reason == "pred_empty"


def test_sql_error_is_pred_error(db: Path) -> None:
    result = exec_match(db, "SELECT name FROM nope", "SELECT name FROM singer")
    assert (result.correct, result.reason) == (False, "pred_error")


def test_multiple_statements(db: Path) -> None:
    # upstream quirk, kept on purpose: with DISTINCT removal only the first statement survives
    assert exec_match(db, "SELECT 1; SELECT 2", "SELECT 1").correct
    result = exec_match(db, "SELECT 1; SELECT 2", "SELECT 1", keep_distinct=True)
    assert (result.correct, result.reason) == (False, "pred_error")


def test_prediction_cannot_modify_database(db: Path) -> None:
    result = exec_match(db, "DELETE FROM singer", "SELECT name FROM singer")
    assert result.reason == "pred_error"
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from singer").fetchone()[0] == len(ROWS)
    con.close()


RUNAWAY = (
    "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c LIMIT 200000000) "
    "SELECT count(*) FROM c"
)


def test_timeout_is_enforced(db: Path) -> None:
    start = time.monotonic()
    result = exec_match(db, RUNAWAY, "SELECT 1", timeout_s=0.3)
    assert (result.correct, result.reason) == (False, "pred_timeout")
    assert time.monotonic() - start < 10


def test_result_cap(db: Path) -> None:
    out = execute(db, "SELECT name FROM singer", max_rows=2)
    assert (out.ok, out.error) == (False, "too_many_rows")
    assert execute(db, "SELECT name FROM singer", max_rows=4).ok


def test_gold_failure_raises(db: Path) -> None:
    with pytest.raises(GoldExecutionError):
        exec_match(db, "SELECT 1", "SELECT * FROM nope")


def test_missing_database_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        exec_match(tmp_path / "x.sqlite", "SELECT 1", "SELECT 1")


def test_gold_cache_is_filled_and_reused(db: Path) -> None:
    cache: dict = {}
    exec_match(db, "SELECT name FROM singer", "SELECT name FROM singer", gold_cache=cache)
    assert len(cache) == 1
    (key,) = cache
    marker = cache[key]
    exec_match(db, "SELECT name FROM singer", "SELECT name FROM singer", gold_cache=cache)
    assert cache[key] is marker


def test_invalid_utf8_text_is_read_leniently(tmp_path: Path) -> None:
    path = tmp_path / "u" / "u.sqlite"
    path.parent.mkdir()
    con = sqlite3.connect(path)
    con.execute("create table t (s text)")
    con.execute("insert into t values (CAST(x'ff41' AS TEXT))")
    con.commit()
    con.close()
    assert exec_match(path, "SELECT s FROM t", "SELECT s FROM t").correct


def test_fast_path_agrees_with_upstream_result_eq() -> None:
    rng = random.Random(7)
    cells = [None, 0, 1, 2, "a", "b"]
    for _ in range(400):
        n_cols = rng.randint(1, 4)
        n_rows = rng.randint(0, 5)
        left = tuple(tuple(rng.choice(cells) for _ in range(n_cols)) for _ in range(n_rows))
        right = list(left)
        if rng.random() < 0.5:
            rng.shuffle(right)
        if rng.random() < 0.4 and n_cols > 1:
            order = rng.sample(range(n_cols), n_cols)
            right = [tuple(row[i] for i in order) for row in right]
        if rng.random() < 0.3 and right:
            right[rng.randrange(len(right))] = tuple(rng.choice(cells) for _ in range(n_cols))
        right_t = tuple(right)
        for order_matters in (False, True):
            expected = result_eq(list(left), list(right_t), order_matters)
            assert _same(left, right_t, order_matters) == expected
