"""Trivial baselines (SPEC section 4). A model that does not beat them is not a result."""

from __future__ import annotations

import re
from collections.abc import Sequence

_WORD = re.compile(r"[a-z0-9]+")


def _stem(token: str) -> str:
    return token[:-1] if len(token) > 3 and token.endswith("s") else token


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in _WORD.findall(text.lower().replace("_", " "))}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def first_table(tables: Sequence[str]) -> str:
    """B0a: SELECT * FROM the first table in schema order."""
    return f"SELECT * FROM {_quote(tables[0])}"


def overlap_count(question: str, tables: Sequence[str]) -> str:
    """B0b: SELECT count(*) FROM the table whose name shares most tokens with the question.

    Tokens: lowercase alphanumerics, '_' splits words, trailing 's' dropped on words longer
    than 3 characters. Ties go to the earlier table in schema order.
    """
    question_tokens = _tokens(question)
    best = max(range(len(tables)), key=lambda i: (len(_tokens(tables[i]) & question_tokens), -i))
    return f"SELECT count(*) FROM {_quote(tables[best])}"
