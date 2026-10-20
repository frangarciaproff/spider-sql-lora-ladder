import pytest

from spider_sql.error_analysis import LABELS, blind_items, failures, sample, summarize, wilson


def test_failures_and_sample_are_deterministic() -> None:
    rows = [{"index": i, "ex": int(i % 3 == 0)} for i in range(30)]
    fails = failures(rows)
    assert fails == [i for i in range(30) if i % 3 != 0]
    assert sample(fails, 5, 1234) == sample(list(reversed(fails)), 5, 1234)
    with pytest.raises(ValueError):
        sample(fails, 100, 1234)


def test_blind_items_hide_condition_in_id() -> None:
    items = blind_items({"c1": [1, 2, 3], "c3": [1, 4, 5]}, seed=7)
    assert [i.item_id for i in items] == [f"E{n:03d}" for n in range(1, 7)]
    pairs = sorted((i.condition, i.index) for i in items)
    assert pairs == [("c1", 1), ("c1", 2), ("c1", 3), ("c3", 1), ("c3", 4), ("c3", 5)]


def test_wilson_known_value() -> None:
    lo, hi = wilson(10, 100)
    assert lo == pytest.approx(0.0552, abs=1e-3)
    assert hi == pytest.approx(0.1744, abs=1e-3)


def test_summarize_checks_labels() -> None:
    key = {"E001": "a", "E002": "a", "E003": "b"}
    labels = {"E001": "wrong_join", "E002": "other", "E003": "syntax_error"}
    out = summarize(labels, key, {"a": 0.5, "b": 0.2})
    a = out["a"]
    assert isinstance(a, dict)
    assert a["labels"]["wrong_join"]["share_of_dev"] == pytest.approx(0.25)
    with pytest.raises(ValueError):
        summarize({"E001": "wrong_join"}, key, {"a": 0.5, "b": 0.2})
    with pytest.raises(ValueError):
        summarize({**labels, "E001": "typo"}, key, {"a": 0.5, "b": 0.2})
    assert LABELS[-1] == "other"
