import sqlite3
from pathlib import Path

from spider_sql.schema import schema_ddl, table_names


def make(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE singer (id int, name text)")
    con.execute("CREATE TABLE concert (id int, singer_id int);")
    con.execute("CREATE INDEX idx ON singer(name)")
    con.commit()
    con.close()
    return path


def test_table_names_in_creation_order(tmp_path: Path) -> None:
    assert table_names(make(tmp_path / "a.sqlite")) == ["singer", "concert"]


def test_schema_ddl_has_tables_only_each_ending_in_semicolon(tmp_path: Path) -> None:
    ddl = schema_ddl(make(tmp_path / "b.sqlite"))
    assert ddl == (
        "CREATE TABLE singer (id int, name text);\n\nCREATE TABLE concert (id int, singer_id int);"
    )
    assert "INDEX" not in ddl
