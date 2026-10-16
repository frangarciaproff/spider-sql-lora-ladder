"""Run with the real files: SPIDER_DIR set, then `make test-data`."""

import pytest

from spider_sql.data import SOURCE_FILES, DataPaths, load_examples, load_train, sqlite_path
from spider_sql.leakage import shared_db_ids, text_overlaps
from spider_sql.split import make_split

pytestmark = pytest.mark.data


def test_counts_match_spider_readme() -> None:
    paths = DataPaths.from_env()
    counts = {s: len(load_examples(paths.spider, s)) for s in SOURCE_FILES}
    assert counts == {"train_spider": 7000, "train_others": 1659, "dev": 1034, "test": 2147}


def test_every_example_has_a_sqlite_file() -> None:
    paths = DataPaths.from_env()
    for source in SOURCE_FILES:
        missing = {
            e.db_id
            for e in load_examples(paths.spider, source)
            if not sqlite_path(paths.spider, source, e.db_id).is_file()
        }
        assert not missing, (source, sorted(missing))


def test_split_is_database_disjoint_and_has_15_validation_dbs() -> None:
    paths = DataPaths.from_env()
    split = make_split(load_train(paths.spider))
    assert len(split.validation_db_ids) == 15
    splits = {
        "fit": split.fit,
        "validation": split.validation,
        "dev": load_examples(paths.spider, "dev"),
        "test": load_examples(paths.spider, "test"),
    }
    assert shared_db_ids(splits) == {}


def test_no_question_sql_pair_overlap_after_cleaning() -> None:
    paths = DataPaths.from_env()
    dev = load_examples(paths.spider, "dev")
    test = load_examples(paths.spider, "test")
    split = make_split(load_train(paths.spider), holdouts={"dev": dev, "test": test})
    assert len(split.removed) > 0
    others = {"validation": split.validation, "dev": dev, "test": test}
    for name, info in text_overlaps(split.fit, others).items():
        assert info["n_question_sql_overlap"] == 0, name
