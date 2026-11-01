"""Small read-only SQLite MCP example; no arbitrary SQL or database-path tool input."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from typing import Annotated, Any, Iterator

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

MAX_DATABASE_BYTES = 64 * 1024 * 1024
MAX_VALUE_BYTES = 2048
MAX_RESULT_BYTES = 32 * 1024
MAX_COLUMNS = 64
QUERY_SECONDS = 1.0

Name = Annotated[str, Field(min_length=1, max_length=128, strict=True)]
PageSize = Annotated[int, Field(ge=1, le=100, strict=True)]
RowLimit = Annotated[int, Field(ge=1, le=50, strict=True)]


class Tables(BaseModel):
    tables: list[str]
    next_after: str | None


class Column(BaseModel):
    name: str
    declared_type: str
    not_null_declared: bool
    primary_key_position: int


class Schema(BaseModel):
    table: str
    columns: list[Column]
    sqlite_version: str


class Preview(BaseModel):
    table: str
    columns: list[str]
    rows: list[list[Any]]
    row_limit: int
    truncated: bool = False
    truncation_reason: str | None = None
    value_truncations: int = 0


def result_bytes(value: BaseModel) -> int:
    return len(json.dumps(value.model_dump(), ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False).encode("utf-8"))


def check_result_size(value: BaseModel) -> None:
    if result_bytes(value) > MAX_RESULT_BYTES:
        raise ValueError("Result exceeds the 32 KiB structured-result limit")


class Database:
    def __init__(self, path: Path):
        self.path = path.resolve(strict=True)
        self._check_file()
        if sqlite3.sqlite_version_info < (3, 37, 0):
            raise ValueError("SQLite 3.37 or newer is required for ordinary-table discovery")

    def _check_file(self) -> None:
        if not self.path.is_file() or self.path.stat().st_size > MAX_DATABASE_BYTES:
            raise ValueError("Use an existing SQLite database file no larger than 64 MiB")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self._check_file()
        connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=0.1)
        deadline = time.monotonic() + QUERY_SECONDS
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            # Bounds are enforced by SQLite before values are materialized in Python.
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 256 * 1024)
            connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 256)
            connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 64 * 1024)
            connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            yield connection
        except sqlite3.Error as exc:
            if exc.sqlite_errorcode in {sqlite3.SQLITE_INTERRUPT, sqlite3.SQLITE_TOOBIG}:
                raise ValueError("SQLite operation exceeded a time or value-size limit") from None
            raise ValueError("SQLite operation failed; check the file, locks and table schema") from None
        finally:
            connection.close()

    @staticmethod
    def _table(connection: sqlite3.Connection, table: str) -> list[str]:
        if len(table.encode("utf-8")) > 128:
            raise ValueError("Table names must be at most 128 UTF-8 bytes")
        entry = connection.execute(
            "SELECT ncol FROM pragma_table_list WHERE schema='main' AND name=? "
            "AND type='table' AND substr(name,1,7) != 'sqlite_'", (table,)
        ).fetchone()
        if entry is None:
            raise ValueError("Unknown ordinary table; use list_tables first")
        if entry[0] > MAX_COLUMNS:
            raise ValueError("This example supports tables with at most 64 columns")
        rows = connection.execute("SELECT name FROM pragma_table_info(?, 'main')", (table,))
        columns = [row[0] for row in rows]
        if not columns or any(len(name.encode("utf-8")) > 128 for name in columns):
            raise ValueError("Column names must be at most 128 UTF-8 bytes")
        return columns

    def list_tables(self, limit: int, after: str) -> Tables:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM pragma_table_list WHERE schema='main' AND type='table' "
                "AND substr(name,1,7) != 'sqlite_' AND name > ? COLLATE BINARY "
                "ORDER BY name COLLATE BINARY LIMIT ?", (after, limit + 1)
            ).fetchall()
            names = [row[0] for row in rows[:limit]]
            if any(len(name.encode("utf-8")) > 128 for name in names):
                raise ValueError("Table names must be at most 128 UTF-8 bytes")
            result = Tables(tables=names, next_after=names[-1] if len(rows) > limit else None)
            check_result_size(result)
            return result

    def describe_table(self, table: str) -> Schema:
        with self.connect() as connection:
            self._table(connection, table)
            rows = connection.execute(
                'SELECT name,type,"notnull",pk FROM pragma_table_info(?, \'main\')', (table,)
            ).fetchall()
            columns = [Column(name=row[0], declared_type=row[1][:128],
                              not_null_declared=bool(row[2]), primary_key_position=row[3]) for row in rows]
            result = Schema(table=table, columns=columns, sqlite_version=sqlite3.sqlite_version)
            check_result_size(result)
            return result

    def preview_rows(self, table: str, limit: int) -> Preview:
        with self.connect() as connection:
            columns = self._table(connection, table)
            quote = lambda identifier: '"' + identifier.replace('"', '""') + '"'
            statement = f"SELECT {','.join(quote(name) for name in columns)} FROM {quote(table)} LIMIT ?"
            cursor = connection.execute(statement, (limit + 1,))
            result = Preview(table=table, columns=columns, rows=[], row_limit=limit)
            # Escaped identifiers alone can exceed the budget, even for an empty table.
            check_result_size(result)
            for raw_row in cursor:
                if len(result.rows) == limit:
                    result.truncated, result.truncation_reason = True, "row_limit"
                    break
                row, clipped = [], 0
                for value in raw_row:
                    if isinstance(value, bytes):
                        row.append({"type": "blob", "bytes": len(value), "hex_preview": value[:32].hex()})
                        clipped += int(len(value) > 32)
                    elif isinstance(value, str):
                        encoded = value.encode("utf-8")
                        row.append(encoded[:MAX_VALUE_BYTES].decode("utf-8", errors="ignore"))
                        clipped += int(len(encoded) > MAX_VALUE_BYTES)
                    elif isinstance(value, float) and not (-float("inf") < value < float("inf")):
                        row.append({"type": "nonfinite_float", "value": str(value)})
                    else:
                        row.append(value)
                result.rows.append(row)
                result.value_truncations += clipped
                # Leave room for the longer truncation metadata in the final result.
                if result_bytes(result) > MAX_RESULT_BYTES - 128:
                    result.rows.pop()
                    result.value_truncations -= clipped
                    result.truncated, result.truncation_reason = True, "byte_limit"
                    break
            check_result_size(result)
            return result


def create_server(database: Database) -> FastMCP:
    server = FastMCP("sqlite-preview")

    @server.tool()
    def list_tables(limit: PageSize = 20, after: Annotated[str, Field(max_length=128, strict=True)] = "") -> Tables:
        """List ordinary tables in binary name order; pass next_after to get another page."""
        return database.list_tables(limit, after)

    @server.tool()
    def describe_table(table: Name) -> Schema:
        """Inspect ordinary table columns, declared types and primary-key positions; never execute SQL input."""
        return database.describe_table(table)

    @server.tool()
    def preview_rows(table: Name, limit: RowLimit = 10) -> Preview:
        """Read up to 50 rows without a guaranteed order; return bounded text and blob previews."""
        return database.preview_rows(table, limit)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Existing operator-selected SQLite file")
    args = parser.parse_args()
    try:
        database = Database(args.database)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    create_server(database).run(transport="stdio")


if __name__ == "__main__":
    main()
