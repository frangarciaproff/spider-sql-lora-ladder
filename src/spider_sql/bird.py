"""BIRD dev as an out-of-distribution test (SPEC 8): loading, prompts and the official metric.

Metric, as in the official evaluation.py (AlibabaResearch/DAMO-ConvAI, bird/llm/src): the
prediction is correct when set(predicted rows) == set(gold rows). Row order and duplicates are
ignored, column order is not. Any error, in the prediction or the gold, scores 0. Timeout 30 s
per query (official: 30 s for both). Text is decoded strictly, as sqlite3 does by default.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from spider_sql.execution import QueryOutcome, execute

SOURCE = "bird_dev"
N_DEV = 1534
N_DATABASES = 11
TIMEOUT_S = 30.0
VARIANTS = {"bird_dev": True, "bird_dev_noev": False}  # file stem -> evidence in prompt


@dataclass(frozen=True)
class BirdExample:
    index: int
    question_id: int
    db_id: str
    question: str
    evidence: str
    query: str
    difficulty: str


@dataclass(frozen=True)
class BirdPaths:
    """questions: dev.json. databases: folder with <db_id>/<db_id>.sqlite."""

    questions: Path
    databases: Path

    @classmethod
    def from_env(cls) -> BirdPaths:
        root, dbs = os.environ.get("BIRD_DIR"), os.environ.get("BIRD_DB_DIR")
        if not root or not dbs:
            raise RuntimeError("BIRD_DIR (folder with dev.json) and BIRD_DB_DIR must be set")
        return cls(questions=Path(root) / "dev.json", databases=Path(dbs))

    def sqlite(self, db_id: str) -> Path:
        return self.databases / db_id / f"{db_id}.sqlite"


def load_bird(questions: Path) -> list[BirdExample]:
    rows = json.loads(questions.read_text(encoding="utf-8"))
    return [
        BirdExample(
            index=i,
            question_id=int(r.get("question_id", i)),
            db_id=r["db_id"],
            question=r["question"],
            evidence=r.get("evidence") or "",
            query=r["SQL"],
            difficulty=r.get("difficulty", "unknown"),
        )
        for i, r in enumerate(rows)
    ]


def question_text(example: BirdExample, with_evidence: bool) -> str:
    """SPEC 8: the evidence is appended to the question; the rest of the template is unchanged."""
    if with_evidence and example.evidence.strip():
        return f"{example.question}\nEvidence: {example.evidence.strip()}"
    return example.question


def run(db: Path, query: str) -> QueryOutcome:
    return execute(db, query, timeout_s=TIMEOUT_S, lenient_text=False)


def bird_match(pred: QueryOutcome, gold: QueryOutcome) -> tuple[int, str]:
    """(score, reason) under the official rule."""
    if not gold.ok:
        return 0, "gold_error"
    if not pred.ok:
        return 0, {"timeout": "pred_timeout", "too_many_rows": "pred_too_many_rows"}.get(
            pred.error, "pred_error"
        )
    return (1, "match") if set(pred.rows) == set(gold.rows) else (0, "mismatch")


def check_counts(examples: list[BirdExample], paths: BirdPaths) -> dict[str, object]:
    """The release we pre-registered: 1,534 questions on 11 databases, all files present."""
    db_ids = sorted({e.db_id for e in examples})
    missing = [d for d in db_ids if not paths.sqlite(d).is_file()]
    problems = []
    if len(examples) != N_DEV:
        problems.append(f"{len(examples)} questions, expected {N_DEV}")
    if len(db_ids) != N_DATABASES:
        problems.append(f"{len(db_ids)} databases, expected {N_DATABASES}")
    if missing:
        problems.append(f"missing sqlite files: {missing}")
    if problems:
        raise ValueError("; ".join(problems))
    by_db: dict[str, int] = {}
    for e in examples:
        by_db[e.db_id] = by_db.get(e.db_id, 0) + 1
    return {"n": len(examples), "databases": by_db}


def summarize(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    def acc(sub: Sequence[Mapping[str, object]]) -> dict[str, object]:
        reasons: dict[str, int] = {}
        for r in sub:
            reasons[str(r["ex_reason"])] = reasons.get(str(r["ex_reason"]), 0) + 1
        n_ok = sum(int(str(r["ex"])) for r in sub)
        return {"n": len(sub), "n_correct": n_ok, "accuracy": n_ok / len(sub), "reasons": reasons}

    levels = sorted({str(r["difficulty"]) for r in rows})
    return {
        "ex": acc(rows),
        "by_difficulty": {lv: acc([r for r in rows if r["difficulty"] == lv]) for lv in levels},
    }
