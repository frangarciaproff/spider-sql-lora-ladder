"""Shared fixtures. Tests marked `data` need the real Spider files and skip otherwise."""

import json
import os
from pathlib import Path

import pytest

from spider_sql.data import Example


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("SPIDER_DIR"):
        return
    skip = pytest.mark.skip(reason="SPIDER_DIR is not set")
    for item in items:
        if "data" in item.keywords:
            item.add_marker(skip)


def make_examples(source: str, db_ids: list[str], per_db: int = 2) -> list[Example]:
    return [
        Example(
            source=source,
            index=i,
            db_id=db_id,
            question=f"question {db_id} {j}",
            query=f"SELECT {j} FROM {db_id}",
        )
        for i, (db_id, j) in enumerate((d, j) for d in db_ids for j in range(per_db))
    ]


def _rows(db_ids: list[str]) -> list[dict[str, str]]:
    return [
        {"db_id": d, "question": f"How many {d}?", "query": f"SELECT count(*) FROM {d}"}
        for d in db_ids
    ]


def _touch(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def spider_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Tiny Spider-shaped tree: train a,b / others c / dev d / test e. Plus junk files."""
    spider, suite = tmp_path / "spider_src", tmp_path / "suite_src"
    layout = {
        "train_spider.json": ["a", "b"],
        "train_others.json": ["c"],
        "dev.json": ["d"],
        "test.json": ["e"],
    }
    for name, dbs in layout.items():
        _touch(spider / name, json.dumps(_rows(dbs)).encode())
    for name in ("README.txt", "tables.json", "test_tables.json", "train_gold.sql"):
        _touch(spider / name)
    for name in ("dev_gold.sql", "test_gold.sql"):
        _touch(spider / name)
    for db in ("a", "b", "c", "d"):
        _touch(spider / "database" / db / f"{db}.sqlite")
    _touch(spider / "database" / "a" / ".DS_Store")
    _touch(spider / "database" / "__MACOSX" / "junk")
    for db in ("e", "zz_not_in_test"):
        _touch(spider / "test_database" / db / f"{db}.sqlite")
    for db in ("d", "d2_not_dev"):
        _touch(suite / "database" / db / f"{db}.sqlite")
    _touch(suite / "database" / "d" / "dv1.sqlite", b"variant")
    return spider, suite
