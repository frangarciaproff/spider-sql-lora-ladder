"""Database-level validation split. Never splits by example."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from spider_sql.data import Example, load_examples, load_train
from spider_sql.leakage import remove_pair_overlaps

SPLIT_SEED = 1234
VAL_FRACTION = 0.10


@dataclass(frozen=True)
class Split:
    fit: tuple[Example, ...]
    validation: tuple[Example, ...]
    validation_db_ids: tuple[str, ...]
    removed: tuple[Example, ...] = ()


def _rank(db_id: str, seed: int) -> str:
    # Hash ranking is stable across Python versions, unlike random.sample.
    return hashlib.sha256(f"{seed}:{db_id}".encode()).hexdigest()


def pick_validation_dbs(
    examples: Sequence[Example],
    fraction: float = VAL_FRACTION,
    seed: int = SPLIT_SEED,
) -> tuple[str, ...]:
    """Pick round(fraction * all train DBs) from train_spider-only DBs.

    DBs that appear in train_others always stay in fit.
    """
    all_dbs = {e.db_id for e in examples}
    others = {e.db_id for e in examples if e.source == "train_others"}
    spider_only = {e.db_id for e in examples if e.source == "train_spider"} - others
    k = round(fraction * len(all_dbs))
    if k > len(spider_only):
        raise ValueError(f"need {k} validation DBs, only {len(spider_only)} eligible")
    ranked = sorted(spider_only, key=lambda db_id: _rank(db_id, seed))
    return tuple(sorted(ranked[:k]))


def make_split(
    examples: Sequence[Example],
    fraction: float = VAL_FRACTION,
    seed: int = SPLIT_SEED,
    holdouts: Mapping[str, Sequence[Example]] | None = None,
) -> Split:
    """Database-level split, then drop fit examples whose (question, SQL) pair also occurs
    in validation or in any holdout split (dev, test)."""
    val_ids = pick_validation_dbs(examples, fraction=fraction, seed=seed)
    val_set = set(val_ids)
    fit = tuple(e for e in examples if e.db_id not in val_set)
    validation = tuple(e for e in examples if e.db_id in val_set)
    blocked = [validation, *(holdouts or {}).values()]
    fit, removed = remove_pair_overlaps(fit, blocked)
    return Split(fit=fit, validation=validation, validation_db_ids=val_ids, removed=removed)


def manifest(
    split: Split,
    fraction: float = VAL_FRACTION,
    seed: int = SPLIT_SEED,
) -> dict[str, object]:
    return {
        "seed": seed,
        "fraction": fraction,
        "validation_db_ids": list(split.validation_db_ids),
        "n_fit": len(split.fit),
        "n_validation": len(split.validation),
        "n_removed_pair_overlap": len(split.removed),
        "n_fit_dbs": len({e.db_id for e in split.fit}),
        "n_validation_dbs": len(split.validation_db_ids),
    }


def load_all_splits(spider_dir: Path) -> dict[str, list[Example]]:
    """fit (decontaminated), validation, dev and test, built exactly as prepare_split.py does."""
    dev = load_examples(spider_dir, "dev")
    test = load_examples(spider_dir, "test")
    split = make_split(load_train(spider_dir), holdouts={"dev": dev, "test": test})
    return {
        "fit": list(split.fit),
        "validation": list(split.validation),
        "dev": dev,
        "test": test,
    }
