"""Compare exec_match with upstream eval_exec_match on real dev data.

Needs SPIDER_DIR, TESTSUITE_DIR and UPSTREAM_TS_DIR (a clone of taoyds/test-suite-sql-eval).
Run: make test-data (with UPSTREAM_TS_DIR set in .env).
"""

import os
import random
import re
import sys
import time
from pathlib import Path

import pytest

from spider_sql.data import DataPaths, load_examples
from spider_sql.execution import exec_match

pytestmark = pytest.mark.data


def mutations(gold: str) -> list[str]:
    out = [gold, gold + " LIMIT 1", "SELEC", gold.replace(" > ", " >= ", 1)]
    out.append(gold.replace("SELECT ", "SELECT DISTINCT ", 1))
    out.append(gold.replace(" < ", " > ", 1))
    out.append(re.sub(r"\bASC\b", "DESC", gold, count=1, flags=re.IGNORECASE))
    out.append(gold + " DESC" if "order by" in gold.lower() else gold + " ORDER BY 1 DESC")
    table = re.search(r"\bFROM\s+(\w+)", gold, flags=re.IGNORECASE)
    if table:
        out.append(f"SELECT * FROM {table.group(1)}")
        out.append(f"SELECT count(*) FROM {table.group(1)}")
    return out


def test_agrees_with_upstream_on_dev() -> None:
    upstream_dir = os.environ.get("UPSTREAM_TS_DIR")
    if not upstream_dir:
        pytest.skip("UPSTREAM_TS_DIR is not set")
    paths = DataPaths.from_env()
    assert paths.testsuite is not None
    sys.path.insert(0, upstream_dir)
    import exec_eval  # upstream module

    examples = load_examples(paths.spider, "dev")
    sample = random.Random(int(os.environ.get("EQUIV_SEED", "0"))).sample(
        examples, int(os.environ.get("EQUIV_N", "120"))
    )
    disagreements = []
    n_true = n_false = 0
    t_theirs = t_ours = 0.0
    for ex in sample:
        db = paths.testsuite / "database" / ex.db_id / f"{ex.db_id}.sqlite"
        for pred in mutations(ex.query):
            if not pred.strip():
                continue
            t0 = time.monotonic()
            theirs = bool(exec_eval.eval_exec_match(str(db), pred, ex.query, False, False, False))
            t1 = time.monotonic()
            ours = exec_match(Path(db), pred, ex.query).correct
            t_theirs += t1 - t0
            t_ours += time.monotonic() - t1
            n_true += theirs
            n_false += not theirs
            if theirs != ours:
                disagreements.append((ex.db_id, pred, theirs, ours))
    print(
        f"compared {n_true + n_false}: upstream true={n_true} false={n_false}; "
        f"seconds upstream={t_theirs:.1f} ours={t_ours:.1f}"
    )
    assert not disagreements, disagreements[:5]
