"""Spider loading and path resolution."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

SOURCE_FILES = {
    "train_spider": "train_spider.json",
    "train_others": "train_others.json",
    "dev": "dev.json",
    "test": "test.json",
}
TRAIN_SOURCES = ("train_spider", "train_others")


@dataclass(frozen=True)
class Example:
    source: str
    index: int
    db_id: str
    question: str
    query: str


@dataclass(frozen=True)
class DataPaths:
    """spider: folder with dev.json. testsuite: folder that contains database/."""

    spider: Path
    testsuite: Path | None

    @classmethod
    def from_env(cls) -> DataPaths:
        spider = os.environ.get("SPIDER_DIR")
        if not spider:
            raise RuntimeError("SPIDER_DIR is not set (folder that contains dev.json).")
        testsuite = os.environ.get("TESTSUITE_DIR")
        return cls(spider=Path(spider), testsuite=Path(testsuite) if testsuite else None)


def load_examples(spider_dir: Path, source: str) -> list[Example]:
    if source not in SOURCE_FILES:
        raise ValueError(f"unknown source {source!r}; expected one of {sorted(SOURCE_FILES)}")
    with (spider_dir / SOURCE_FILES[source]).open(encoding="utf-8") as handle:
        rows = json.load(handle)
    return [
        Example(
            source=source,
            index=i,
            db_id=row["db_id"],
            question=row["question"],
            query=row["query"],
        )
        for i, row in enumerate(rows)
    ]


def load_train(spider_dir: Path) -> list[Example]:
    return [e for source in TRAIN_SOURCES for e in load_examples(spider_dir, source)]


def sqlite_path(spider_dir: Path, source: str, db_id: str) -> Path:
    folder = "test_database" if source == "test" else "database"
    return spider_dir / folder / db_id / f"{db_id}.sqlite"


def normalize_question(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def normalize_sql(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().rstrip(";").strip().lower())
