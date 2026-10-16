import json
from pathlib import Path

import pytest

from spider_sql.data import (
    DataPaths,
    load_examples,
    load_train,
    normalize_question,
    normalize_sql,
    sqlite_path,
)


def test_load_examples(spider_tree: tuple[Path, Path]) -> None:
    spider, _ = spider_tree
    rows = load_examples(spider, "dev")
    assert len(rows) == 1
    assert (rows[0].source, rows[0].index, rows[0].db_id) == ("dev", 0, "d")


def test_load_examples_unknown_source(spider_tree: tuple[Path, Path]) -> None:
    with pytest.raises(ValueError):
        load_examples(spider_tree[0], "nope")


def test_load_train_concatenates_both_files(spider_tree: tuple[Path, Path]) -> None:
    rows = load_train(spider_tree[0])
    assert [(e.source, e.db_id) for e in rows] == [
        ("train_spider", "a"),
        ("train_spider", "b"),
        ("train_others", "c"),
    ]


def test_sqlite_path_test_uses_test_database(tmp_path: Path) -> None:
    assert sqlite_path(tmp_path, "test", "x") == tmp_path / "test_database" / "x" / "x.sqlite"
    assert sqlite_path(tmp_path, "dev", "x") == tmp_path / "database" / "x" / "x.sqlite"
    assert sqlite_path(tmp_path, "train_spider", "x") == tmp_path / "database" / "x" / "x.sqlite"


def test_normalize() -> None:
    assert normalize_question("  How   MANY\nsingers? ") == "how many singers?"
    assert normalize_sql("SELECT  count(*)\nFROM t ; ") == "select count(*) from t"


def test_data_paths_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SPIDER_DIR", raising=False)
    with pytest.raises(RuntimeError):
        DataPaths.from_env()
    monkeypatch.setenv("SPIDER_DIR", str(tmp_path))
    monkeypatch.delenv("TESTSUITE_DIR", raising=False)
    paths = DataPaths.from_env()
    assert paths.spider == tmp_path
    assert paths.testsuite is None
    monkeypatch.setenv("TESTSUITE_DIR", str(tmp_path / "t"))
    assert DataPaths.from_env().testsuite == tmp_path / "t"


def test_load_examples_reads_utf8(tmp_path: Path) -> None:
    row = {"db_id": "d", "question": "¿Cuántos años?", "query": "SELECT 1"}
    (tmp_path / "dev.json").write_text(json.dumps([row]), encoding="utf-8")
    assert load_examples(tmp_path, "dev")[0].question == "¿Cuántos años?"
