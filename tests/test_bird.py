import importlib.util
import json
import sqlite3
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

from spider_sql.bird import (
    BirdExample,
    BirdPaths,
    bird_match,
    check_counts,
    load_bird,
    question_text,
    run,
)
from spider_sql.execution import QueryOutcome

ROOT = Path(__file__).parents[1]


def script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE t (a INT, b TEXT); INSERT INTO t VALUES (1, 'x'), (2, 'y'), (2, 'y');"
    )
    con.execute("INSERT INTO t VALUES (3, CAST(X'FF' AS TEXT))")
    con.commit()
    con.close()
    return path


def ok(*rows: tuple[object, ...]) -> QueryOutcome:
    return QueryOutcome(ok=True, rows=tuple(rows))


def test_official_rule_is_set_equality_with_column_order() -> None:
    assert bird_match(ok((1, "x"), (1, "x")), ok((1, "x"))) == (1, "match")  # duplicates
    assert bird_match(ok((2, "y"), (1, "x")), ok((1, "x"), (2, "y"))) == (1, "match")  # order
    assert bird_match(ok(("x", 1)), ok((1, "x"))) == (0, "mismatch")  # column order matters
    assert bird_match(ok(), QueryOutcome(ok=False, error="boom")) == (0, "gold_error")
    assert bird_match(QueryOutcome(ok=False, error="timeout"), ok()) == (0, "pred_timeout")


def test_strict_text_decoding(tmp_path: Path) -> None:
    db = make_db(tmp_path / "d" / "d.sqlite")
    assert run(db, "SELECT a FROM t WHERE a < 3").ok
    assert not run(db, "SELECT b FROM t").ok  # invalid UTF-8 is an error, as in BIRD's script


def test_question_text() -> None:
    e = BirdExample(0, 0, "d", "How many?", " count = rows ", "SELECT 1", "simple")
    assert question_text(e, True) == "How many?\nEvidence: count = rows"
    assert question_text(e, False) == "How many?"
    assert question_text(BirdExample(0, 0, "d", "Q", "", "S", "simple"), True) == "Q"


def write_release(root: Path, n: int = 3) -> None:
    make_db(root / "dev_databases" / "d" / "d.sqlite")
    rows = [
        {
            "question_id": i,
            "db_id": "d",
            "question": "q",
            "evidence": "",
            "SQL": "SELECT 1",
            "difficulty": "simple",
        }
        for i in range(n)
    ]
    (root / "dev.json").write_text(json.dumps(rows), encoding="utf-8")


def test_check_counts_rejects_other_releases(tmp_path: Path) -> None:
    write_release(tmp_path)
    paths = BirdPaths(tmp_path / "dev.json", tmp_path / "dev_databases")
    with pytest.raises(ValueError, match="expected 1534"):
        check_counts(load_bird(paths.questions), paths)


def test_locate_handles_nested_zip(tmp_path: Path) -> None:
    src = tmp_path / "src"
    write_release(src)
    inner = tmp_path / "dev_release" / "dev_databases.zip"
    inner.parent.mkdir()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.write(src / "dev_databases" / "d" / "d.sqlite", "dev_databases/d/d.sqlite")
        zf.writestr("__MACOSX/dev_databases/d/._d.sqlite", "junk")
    (tmp_path / "dev_release" / "dev.json").write_text((src / "dev.json").read_text())
    paths = script("get_bird").locate(tmp_path / "dev_release", tmp_path / "out")
    assert paths.questions == tmp_path / "dev_release" / "dev.json"
    assert paths.sqlite("d").is_file()
    assert not (tmp_path / "out" / "inner" / "__MACOSX").exists()


def test_decision_rules() -> None:
    ev = script("evaluate_bird")
    assert ev.decide_o1({"point": 0.03, "lo": 0.001}, 3) == "SUCCESS"
    assert ev.decide_o1({"point": 0.019, "lo": 0.001}, 3) == "NOT MET"
    assert ev.decide_o1({"point": 0.05, "lo": -0.001}, 3) == "NOT MET"
    assert ev.decide_o2({"point": -0.01, "lo": -0.02}, 3) == "SUCCESS"
    assert ev.decide_o2({"point": 0.01, "lo": -0.021}, 3) == "NOT MET"
    assert ev.decide_o2({"point": 0.1, "lo": 0.05}, 2) == "EXPLORATORY"
    assert (ev.O1_MIN_GAIN, ev.O2_MIN_LOWER) == (0.02, -0.02)


def test_score_bird_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_release(tmp_path / "bird")
    monkeypatch.setenv("BIRD_DIR", str(tmp_path / "bird"))
    monkeypatch.setenv("BIRD_DB_DIR", str(tmp_path / "bird" / "dev_databases"))
    preds = tmp_path / "pred"
    preds.mkdir()
    lines = [
        {"index": 0, "pred": "SELECT 1"},
        {"index": 1, "pred": "SELECT 2"},
        {"index": 2, "pred": ""},
    ]
    (preds / "bird_dev.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert (
        script("score_bird").main(["--pred-dir", str(preds), "--out-dir", str(tmp_path / "r")]) == 0
    )
    rows = [json.loads(x) for x in (tmp_path / "r" / "bird_dev.jsonl").read_text().splitlines()]
    assert [(r["ex"], r["ex_reason"]) for r in rows] == [
        (1, "match"),
        (0, "mismatch"),
        (0, "pred_empty"),
    ]


def test_gold_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_release(tmp_path / "bird")
    monkeypatch.setenv("BIRD_DIR", str(tmp_path / "bird"))
    monkeypatch.setenv("BIRD_DB_DIR", str(tmp_path / "bird" / "dev_databases"))
    assert script("score_bird").main(["--gold-check"]) == 0
    assert "1.0000 (3/3)" in capsys.readouterr().out
