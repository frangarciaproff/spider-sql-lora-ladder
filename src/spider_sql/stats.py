"""Paired statistics for SPEC 7.2: db-cluster bootstrap of accuracy differences, seed averaging,
and an exact McNemar test."""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

Key = tuple[str, int]


def load_rows(path: Path) -> dict[Key, dict[str, object]]:
    rows: dict[Key, dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[(str(row["source"]), int(row["index"]))] = row
    return rows


def seed_average(
    runs: Sequence[Mapping[Key, Mapping[str, object]]], metric: str
) -> dict[Key, float]:
    """Per-question correctness averaged over seeds (SPEC 7.2); runs must share keys."""
    keys = set(runs[0])
    if any(set(r) != keys for r in runs):
        raise ValueError("runs cover different examples")
    return {k: sum(float(str(r[k][metric])) for r in runs) / len(runs) for k in keys}


def paired_cluster_bootstrap(
    a: Mapping[Key, float],
    b: Mapping[Key, float],
    clusters: Mapping[Key, str],
    n_boot: int = 10_000,
    seed: int = 0,
    level: float = 0.95,
) -> dict[str, float]:
    """Mean of (b - a) over questions, with a percentile interval from resampling whole clusters
    (databases) with replacement."""
    if set(a) != set(b):
        raise ValueError("a and b cover different examples")
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for key in a:
        by_cluster[clusters[key]].append(b[key] - a[key])
    names = sorted(by_cluster)
    sums = {n: sum(v) for n, v in by_cluster.items()}
    counts = {n: len(v) for n, v in by_cluster.items()}
    point = sum(sums.values()) / sum(counts.values())
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        sample = [rng.choice(names) for _ in names]
        draws.append(sum(sums[n] for n in sample) / sum(counts[n] for n in sample))
    draws.sort()
    tail = (1 - level) / 2
    lo = draws[int(math.floor(tail * n_boot))]
    hi = draws[int(math.ceil((1 - tail) * n_boot)) - 1]
    return {
        "point": point,
        "lo": lo,
        "hi": hi,
        "n": float(len(a)),
        "n_clusters": float(len(names)),
        "n_boot": float(n_boot),
        "level": level,
    }


def mcnemar_exact(a: Mapping[Key, int], b: Mapping[Key, int]) -> dict[str, float]:
    """Two-sided exact McNemar test on discordant pairs. a_only: a right, b wrong."""
    if set(a) != set(b):
        raise ValueError("a and b cover different examples")
    a_only = sum(1 for k in a if a[k] == 1 and b[k] == 0)
    b_only = sum(1 for k in a if a[k] == 0 and b[k] == 1)
    n = a_only + b_only
    if n == 0:
        return {"a_only": 0.0, "b_only": 0.0, "p_value": 1.0}
    tail = sum(math.comb(n, i) for i in range(min(a_only, b_only) + 1)) / 2**n
    return {"a_only": float(a_only), "b_only": float(b_only), "p_value": min(1.0, 2 * tail)}
