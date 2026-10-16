import pytest

from conftest import make_examples
from spider_sql.data import Example
from spider_sql.split import make_split, manifest, pick_validation_dbs

SPIDER_DBS = [f"s{i:02d}" for i in range(20)]
OTHERS_DBS = ["o1", "o2"]


def train() -> list:
    return make_examples("train_spider", SPIDER_DBS) + make_examples("train_others", OTHERS_DBS)


def test_k_is_rounded_fraction_of_all_train_dbs() -> None:
    # 22 DBs * 0.10 = 2.2 -> 2
    assert len(pick_validation_dbs(train())) == 2


def test_validation_is_database_disjoint_from_fit() -> None:
    split = make_split(train())
    fit_dbs = {e.db_id for e in split.fit}
    val_dbs = {e.db_id for e in split.validation}
    assert fit_dbs.isdisjoint(val_dbs)
    assert val_dbs == set(split.validation_db_ids)
    assert len(split.fit) + len(split.validation) == len(train())


def test_train_others_dbs_never_in_validation() -> None:
    for seed in range(30):
        assert not set(pick_validation_dbs(train(), seed=seed)) & set(OTHERS_DBS)


def test_db_in_both_sources_stays_in_fit() -> None:
    rows = make_examples("train_spider", SPIDER_DBS) + make_examples("train_others", ["s00"])
    for seed in range(30):
        assert "s00" not in pick_validation_dbs(rows, fraction=0.5, seed=seed)


def test_deterministic_and_order_independent() -> None:
    rows = train()
    assert pick_validation_dbs(rows) == pick_validation_dbs(list(reversed(rows)))
    assert pick_validation_dbs(rows) == pick_validation_dbs(rows)


def test_seed_changes_selection() -> None:
    picks = {pick_validation_dbs(train(), seed=s) for s in range(10)}
    assert len(picks) > 1


def test_too_many_requested_raises() -> None:
    with pytest.raises(ValueError):
        pick_validation_dbs(train(), fraction=0.99)


def test_manifest_counts() -> None:
    split = make_split(train())
    info = manifest(split)
    assert info["n_validation_dbs"] == 2
    assert info["n_fit"] == len(split.fit)
    assert info["n_validation"] == len(split.validation)
    assert info["seed"] == 1234


def test_pair_overlaps_with_validation_and_holdouts_are_removed_from_fit() -> None:
    rows = train()
    val_dbs = pick_validation_dbs(rows)
    in_val = next(e for e in rows if e.db_id == val_dbs[0])
    in_fit = next(e for e in rows if e.db_id not in val_dbs)
    dev = [Example("dev", 0, "dx", in_fit.question, in_fit.query)]
    clean = make_split(rows, holdouts={"dev": dev})
    leaky = rows + [Example("train_spider", 99, "s00", in_val.question, in_val.query)]
    leaky_split = make_split(leaky, holdouts={"dev": dev})
    assert in_fit not in clean.fit
    assert in_fit in clean.removed
    assert len(leaky_split.removed) == len(clean.removed) + 1
    assert all(e.db_id not in set(clean.validation_db_ids) for e in clean.fit)


def test_manifest_reports_removed() -> None:
    rows = train()
    dev = [Example("dev", 0, "dx", rows[0].question, rows[0].query)]
    split = make_split(rows, holdouts={"dev": dev})
    assert manifest(split)["n_removed_pair_overlap"] == len(split.removed) > 0
