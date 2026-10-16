import sqlite3
from pathlib import Path

import pytest

from spider_sql.data import DataPaths, Example
from spider_sql.evaluate import METRICS, database_path, score_split


def make_db(path: Path, ages: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("create table singer (name text, age int)")
    con.executemany("insert into singer values (?, ?)", [(f"s{i}", a) for i, a in enumerate(ages)])
    con.commit()
    con.close()


@pytest.fixture
def paths(tmp_path: Path) -> DataPaths:
    spider, suite = tmp_path / "spider", tmp_path / "suite"
    make_db(spider / "database" / "d" / "d.sqlite", [20, 40])
    make_db(spider / "test_database" / "e" / "e.sqlite", [20, 40])
    make_db(suite / "database" / "d" / "d.sqlite", [20, 40])
    make_db(suite / "database" / "d" / "d_v.sqlite", [30, 40, 40])
    return DataPaths(spider=spider, testsuite=suite)


GOLD = "SELECT count(*) FROM singer WHERE age > 30"


def ex(source: str, db_id: str) -> Example:
    return Example(source=source, index=0, db_id=db_id, question="q", query=GOLD)


def test_metrics_per_split_match_spec() -> None:
    names = {split: [m.name for m in ms] for split, ms in METRICS.items()}
    assert names == {
        "validation": ["ex"],
        "dev": ["ex", "ts", "ts_strict"],
        "test": ["ex", "ex_strict"],
    }


def test_database_path(paths: DataPaths) -> None:
    ex_metric, ts_metric = METRICS["dev"][0], METRICS["dev"][1]
    assert database_path(paths, ex_metric, ex("dev", "d")) == paths.spider / "database/d/d.sqlite"
    assert (
        database_path(paths, ts_metric, ex("dev", "d")) == paths.testsuite / "database/d/d.sqlite"
    )
    test_ex = METRICS["test"][0]
    assert (
        database_path(paths, test_ex, ex("test", "e")) == paths.spider / "test_database/e/e.sqlite"
    )


def test_dev_ex_passes_but_ts_catches_wrong_boundary(paths: DataPaths) -> None:
    pred = "SELECT count(*) FROM singer WHERE age >= 30"
    result = score_split("dev", [ex("dev", "d")], [pred], paths)
    row = result["per_example"][0]
    assert (row["ex"], row["ts"], row["ts_strict"]) == (1, 0, 0)
    assert row["ts_reason"] == "mismatch"
    summary = result["summary"]
    assert summary["ex"]["accuracy"] == 1.0
    assert summary["ts"]["reasons"] == {"mismatch": 1}


def test_length_mismatch_raises(paths: DataPaths) -> None:
    with pytest.raises(ValueError):
        score_split("test", [ex("test", "e")], [], paths)


def test_no_question_text_in_output(paths: DataPaths) -> None:
    result = score_split("test", [ex("test", "e")], [GOLD], paths)
    assert "question" not in result["per_example"][0]
    assert result["summary"]["ex_strict"]["n_correct"] == 1


def test_write_scores_files(paths: DataPaths, tmp_path: Path) -> None:
    import json

    from spider_sql.evaluate import write_scores

    result = score_split(
        "test", [ex("test", "e"), ex("test", "e")], [GOLD, "SELECT 2"], paths
    )  # gold count is 1, so 2 is wrong
    summary_path, rows_path = write_scores(result, tmp_path / "out", "test")
    assert json.loads(summary_path.read_text())["ex"]["n_correct"] == 1
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    assert [r["ex"] for r in rows] == [1, 0]
