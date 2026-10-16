"""Schema text and table names read from the SQLite file itself."""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

_TABLES_SQL = (
    "SELECT name, sql FROM sqlite_master "
    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL "
    "ORDER BY rowid"
)


@lru_cache(maxsize=512)
def _tables(path: str) -> tuple[tuple[str, str], ...]:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        return tuple((name, sql) for name, sql in connection.execute(_TABLES_SQL))
    finally:
        connection.close()


def table_names(sqlite_path: Path) -> list[str]:
    """Tables in creation order."""
    return [name for name, _ in _tables(str(sqlite_path))]


def schema_ddl(sqlite_path: Path) -> str:
    """CREATE TABLE statements in creation order, one blank line apart."""
    statements = [sql.strip().rstrip(";") + ";" for _, sql in _tables(str(sqlite_path))]
    return "\n\n".join(statements)
