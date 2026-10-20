"""Error analysis (SPEC 9): blind sampling of dev failures and summary of manual labels.

A failure is a dev example with EX = 0 on its own database. The two conditions are sampled
separately, then pooled and shuffled under neutral item ids, so the labeler does not know
which condition produced a prediction. The item-to-condition key is written to its own file.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# Fixed before labeling (SPEC 9). When several apply, the first one in this order is used,
# because an earlier error blocks judging the later ones.
LABELS = (
    "syntax_error",
    "hallucinated_schema",
    "wrong_join",
    "wrong_aggregation",
    "wrong_filter_value",
    "other",
)


@dataclass(frozen=True)
class Item:
    item_id: str
    condition: str
    index: int


def failures(rows: Sequence[Mapping[str, object]]) -> list[int]:
    """Indices of the examples whose EX is 0, sorted."""
    return sorted(int(str(r["index"])) for r in rows if int(str(r["ex"])) == 0)


def sample(indices: Sequence[int], n: int, seed: int) -> list[int]:
    if n > len(indices):
        raise ValueError(f"asked for {n} failures, only {len(indices)} exist")
    return sorted(random.Random(seed).sample(sorted(indices), n))


def blind_items(samples: Mapping[str, Sequence[int]], seed: int) -> list[Item]:
    pooled = [(cond, idx) for cond in sorted(samples) for idx in samples[cond]]
    random.Random(seed).shuffle(pooled)
    return [Item(f"E{i:03d}", cond, idx) for i, (cond, idx) in enumerate(pooled, start=1)]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarize(
    labels: Mapping[str, str],
    key: Mapping[str, str],
    failure_rate: Mapping[str, float],
) -> dict[str, object]:
    """labels: item_id -> label. key: item_id -> condition. failure_rate: condition -> share of
    dev examples that fail. Returns per condition the share of failures per label (Wilson 95%
    CI) and that share times the failure rate, i.e. the estimated share of all dev examples."""
    missing = sorted(set(key) - set(labels))
    if missing:
        raise ValueError(f"{len(missing)} items unlabeled, first: {missing[:5]}")
    bad = sorted({v for v in labels.values() if v not in LABELS})
    if bad:
        raise ValueError(f"unknown labels {bad}; allowed {LABELS}")
    out: dict[str, object] = {}
    for cond in sorted(set(key.values())):
        ids = [i for i, c in key.items() if c == cond]
        counts = Counter(labels[i] for i in ids)
        n = len(ids)
        per: dict[str, object] = {}
        for label in LABELS:
            k = counts.get(label, 0)
            lo, hi = wilson(k, n)
            rate = failure_rate[cond]
            per[label] = {
                "count": k,
                "share_of_failures": k / n,
                "ci95": [lo, hi],
                "share_of_dev": k / n * rate,
                "share_of_dev_ci95": [lo * rate, hi * rate],
            }
        out[cond] = {"n_labeled": n, "failure_rate": failure_rate[cond], "labels": per}
    return out
