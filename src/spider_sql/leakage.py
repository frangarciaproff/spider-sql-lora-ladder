"""Leakage checks between splits."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from spider_sql.data import Example, normalize_question, normalize_sql

MAX_SAMPLES = 5


def pair_key(example: Example) -> tuple[str, str]:
    return normalize_question(example.question), normalize_sql(example.query)


def remove_pair_overlaps(
    fit: Sequence[Example],
    holdouts: Sequence[Sequence[Example]],
) -> tuple[tuple[Example, ...], tuple[Example, ...]]:
    """Drop fit examples whose (question, SQL) pair also occurs in any holdout split."""
    blocked = {pair_key(e) for rows in holdouts for e in rows}
    kept = tuple(e for e in fit if pair_key(e) not in blocked)
    removed = tuple(e for e in fit if pair_key(e) in blocked)
    return kept, removed


def shared_db_ids(splits: Mapping[str, Sequence[Example]]) -> dict[str, list[str]]:
    """Map 'a|b' to the db_ids shared by splits a and b. Empty dict means no leakage."""
    names = sorted(splits)
    dbs = {name: {e.db_id for e in splits[name]} for name in names}
    out: dict[str, list[str]] = {}
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            shared = sorted(dbs[left] & dbs[right])
            if shared:
                out[f"{left}|{right}"] = shared
    return out


def text_overlaps(
    fit: Sequence[Example],
    others: Mapping[str, Sequence[Example]],
) -> dict[str, dict[str, object]]:
    """Per other split: examples whose question, or (question, SQL), also occurs in fit."""
    fit_questions = {normalize_question(e.question) for e in fit}
    fit_pairs = {pair_key(e) for e in fit}
    out: dict[str, dict[str, object]] = {}
    for name in sorted(others):
        q_hits = [e for e in others[name] if normalize_question(e.question) in fit_questions]
        pair_hits = [e for e in others[name] if pair_key(e) in fit_pairs]
        out[name] = {
            "n_examples": len(others[name]),
            "n_question_overlap": len(q_hits),
            "n_question_sql_overlap": len(pair_hits),
            "question_samples": [e.question for e in q_hits[:MAX_SAMPLES]],
            "question_sql_samples": [
                {"question": e.question, "query": e.query} for e in pair_hits[:MAX_SAMPLES]
            ],
        }
    return out


def leakage_report(
    splits: Mapping[str, Sequence[Example]],
    fit_name: str = "fit",
) -> dict[str, object]:
    others = {name: rows for name, rows in splits.items() if name != fit_name}
    return {
        "shared_db_ids": shared_db_ids(splits),
        "text_overlaps": text_overlaps(splits[fit_name], others),
    }
