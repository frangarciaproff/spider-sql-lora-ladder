import pytest

from spider_sql.prompt import (
    SYSTEM_PROMPT,
    Shot,
    build_messages,
    extract_sql,
    training_messages,
    user_message,
)


def test_zero_shot_messages() -> None:
    messages = build_messages("CREATE TABLE t (a int);", "How many?")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert messages[1]["content"] == user_message("CREATE TABLE t (a int);", "How many?")
    assert messages[1]["content"].endswith("Question: How many?")


def test_few_shot_turns_precede_the_question() -> None:
    shots = [Shot("S1", "Q1", "SELECT 1"), Shot("S2", "Q2", "SELECT 2")]
    roles = [m["role"] for m in build_messages("S", "Q", shots)]
    assert roles == ["system", "user", "assistant", "user", "assistant", "user"]


def test_training_messages_end_with_gold() -> None:
    messages = training_messages("S", "Q", "SELECT 1")
    assert messages[-1] == {"role": "assistant", "content": "SELECT 1"}
    assert messages[:-1] == build_messages("S", "Q")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("SELECT a FROM t", "SELECT a FROM t"),
        ("SELECT a FROM t;", "SELECT a FROM t"),
        ("```sql\nSELECT a FROM t;\n```", "SELECT a FROM t"),
        ("```\nSELECT a FROM t\n```\nThis query selects a.", "SELECT a FROM t"),
        ("Here it is:\n```sql\nSELECT 1;\n```", "SELECT 1"),
        ("SELECT 1; SELECT 2", "SELECT 1"),
        ("  \n SELECT 1 \n", "SELECT 1"),
        ("", ""),
        ("``` ```", ""),
    ],
)
def test_extract_sql(text: str, expected: str) -> None:
    assert extract_sql(text) == expected


def _fit() -> list:
    from spider_sql.data import Example

    rows = []
    for db in ["a", "b", "c", "d", "big"]:
        for i in range(4):
            rows.append(Example("train_spider", len(rows), db, f"q {db} {i}", f"SELECT {i}"))
    return rows


def test_select_shots_distinct_dbs_deterministic_and_size_limited() -> None:
    from spider_sql.prompt import select_shots

    def schema_of(e) -> str:
        return "x" * (5000 if e.db_id == "big" else 100)

    shots = select_shots(_fit(), schema_of)
    assert len(shots) == 3
    assert len({s.db_id for s in shots}) == 3
    assert "big" not in {s.db_id for s in shots}
    assert shots == select_shots(list(reversed(_fit())), schema_of)


def test_select_shots_raises_when_not_enough() -> None:
    from spider_sql.prompt import select_shots

    with pytest.raises(ValueError):
        select_shots(_fit(), lambda e: "x" * 5000)
