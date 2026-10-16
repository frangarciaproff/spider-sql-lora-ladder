from conftest import make_examples
from spider_sql.data import Example
from spider_sql.leakage import leakage_report, remove_pair_overlaps, shared_db_ids, text_overlaps


def ex(db_id: str, question: str, query: str) -> Example:
    return Example(source="x", index=0, db_id=db_id, question=question, query=query)


def test_clean_splits_have_no_shared_dbs() -> None:
    splits = {"fit": make_examples("x", ["a"]), "dev": make_examples("x", ["b"])}
    assert shared_db_ids(splits) == {}


def test_shared_db_is_reported() -> None:
    splits = {
        "fit": make_examples("x", ["a", "b"]),
        "dev": make_examples("x", ["b"]),
        "test": make_examples("x", ["c"]),
    }
    assert shared_db_ids(splits) == {"dev|fit": ["b"]}


def test_text_overlap_detects_question_and_pair_ignoring_case_and_spacing() -> None:
    fit = [ex("a", "How many singers?", "SELECT count(*) FROM singer")]
    dev = [
        ex("b", "  how many   SINGERS? ", "select count(*)  from singer;"),
        ex("b", "How many singers?", "SELECT 1"),
        ex("b", "Something else", "SELECT 2"),
    ]
    info = text_overlaps(fit, {"dev": dev})["dev"]
    assert info["n_examples"] == 3
    assert info["n_question_overlap"] == 2
    assert info["n_question_sql_overlap"] == 1


def test_report_structure() -> None:
    splits = {"fit": make_examples("x", ["a"]), "dev": make_examples("x", ["b"])}
    report = leakage_report(splits)
    assert report["shared_db_ids"] == {}
    assert set(report["text_overlaps"]) == {"dev"}  # type: ignore[call-overload]


def test_remove_pair_overlaps_keeps_question_only_matches() -> None:
    fit = [
        ex("a", "How many singers?", "SELECT count(*) FROM singer"),
        ex("a", "How many singers?", "SELECT count(*) FROM singer"),
        ex("a", "How many singers?", "SELECT 1"),
        ex("a", "Other", "SELECT 2"),
    ]
    dev = [ex("b", " how many  SINGERS?", "select count(*) from singer ;")]
    test = [ex("c", "Other", "SELECT 3")]
    kept, removed = remove_pair_overlaps(fit, [dev, test])
    assert len(removed) == 2
    assert [e.query for e in kept] == ["SELECT 1", "SELECT 2"]


def test_remove_pair_overlaps_with_no_holdouts_is_identity() -> None:
    fit = make_examples("x", ["a"])
    kept, removed = remove_pair_overlaps(fit, [])
    assert kept == tuple(fit)
    assert removed == ()
