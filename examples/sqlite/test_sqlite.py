"""Behavior checks against the real SQLite library and MCP subprocess transport."""
import importlib.util
from pathlib import Path
import sqlite3
import sys

import pytest


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sample = load("sqlite_example_sample", "make_sample.py")
adapter = load("sqlite_example_adapter", "server.py")


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "sample.sqlite"
    sample.make_sample(path)
    return path


def test_database_mode_rejects_writes(database):
    service = adapter.Database(database)
    with service.connect() as connection:
        # Prove SQLite's file mode enforces read-only even with query_only disabled.
        connection.execute("PRAGMA query_only=OFF")
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM materials")
    assert len(service.preview_rows("materials", 50).rows) == 3


def test_sample_never_overwrites(database):
    original = database.read_bytes()
    with pytest.raises(FileExistsError):
        sample.make_sample(database)
    assert database.read_bytes() == original


def test_preview_clips_values_and_total_size(database):
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE large(text TEXT, data BLOB)")
        connection.executemany("INSERT INTO large VALUES(?,?)", [("界" * 5000, b"x" * 100) for _ in range(40)])
    service = adapter.Database(database)
    preview = service.preview_rows("large", 50)
    assert preview.truncation_reason == "byte_limit"
    assert 1 <= len(preview.rows) < 40
    assert adapter.result_bytes(preview) <= adapter.MAX_RESULT_BYTES
    assert len(preview.rows[0][0].encode()) <= 2048
    assert preview.rows[0][1] == {"type": "blob", "bytes": 100, "hex_preview": (b"x" * 32).hex()}
    assert preview.value_truncations == len(preview.rows) * 2


def test_oversized_sqlite_value_is_rejected(database):
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE too_large(value BLOB)")
        connection.execute("INSERT INTO too_large VALUES(?)", (b"x" * (300 * 1024),))
    with pytest.raises(ValueError, match="size limit"):
        adapter.Database(database).preview_rows("too_large", 1)


def test_escaped_table_names_obey_result_budget(database):
    # These are legal 128-byte identifiers, but each control byte becomes six
    # JSON bytes. A raw identifier-length check cannot enforce response size.
    names = [f"t{index:03}" + "\x01" * 124 for index in range(100)]
    with sqlite3.connect(database) as connection:
        for name in names:
            connection.execute(f'CREATE TABLE "{name}" (value TEXT)')
    service = adapter.Database(database)
    with pytest.raises(ValueError, match="32 KiB"):
        service.list_tables(100, "")
    smaller_page = service.list_tables(20, "")
    assert len(smaller_page.tables) == 20
    assert smaller_page.next_after is not None
    assert adapter.result_bytes(smaller_page) <= adapter.MAX_RESULT_BYTES


def test_empty_table_escaped_column_metadata_obeys_budget(database):
    names = [f"c{index:03}" + "\x01" * 124 for index in range(64)]
    declarations = ",".join(f'"{name}" TEXT' for name in names)
    with sqlite3.connect(database) as connection:
        connection.execute(f"CREATE TABLE wide_empty({declarations})")
    service = adapter.Database(database)
    with pytest.raises(ValueError, match="32 KiB"):
        service.describe_table("wide_empty")
    with pytest.raises(ValueError, match="32 KiB"):
        service.preview_rows("wide_empty", 1)


def test_quoted_identifiers_and_views(database):
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE "odd\""name" ("a\""b" TEXT)')
        connection.execute('INSERT INTO "odd\""name" VALUES(?)', ("quoted identifiers work",))
        connection.execute("CREATE VIEW hidden_view AS SELECT * FROM materials")
    service = adapter.Database(database)
    assert service.preview_rows('odd"name', 1).rows == [["quoted identifiers work"]]
    assert "hidden_view" not in service.list_tables(100, "").tables
    with pytest.raises(ValueError, match="ordinary table"):
        service.preview_rows("hidden_view", 1)


def test_sqlite_progress_deadline_interrupts_work(database, monkeypatch):
    # An expired budget triggers the actual SQLite progress handler, without sleeping.
    monkeypatch.setattr(adapter, "QUERY_SECONDS", 0)
    with pytest.raises(ValueError, match="time or value-size limit"):
        with adapter.Database(database).connect() as connection:
            connection.execute(
                "WITH RECURSIVE numbers(n) AS (VALUES(0) UNION ALL SELECT n+1 FROM numbers "
                "WHERE n<1000000) SELECT sum(n) FROM numbers"
            ).fetchone()


@pytest.mark.asyncio
async def test_real_mcp_calls(database):
    # verify.py is also the standalone acceptance command. Loading its sample import
    # explicitly avoids dependence on pytest's import mode or other examples' names.
    previous = sys.modules.get("make_sample")
    sys.modules["make_sample"] = sample
    try:
        acceptance = load("sqlite_example_verify", "verify.py")
    finally:
        if previous is None:
            sys.modules.pop("make_sample", None)
        else:
            sys.modules["make_sample"] = previous
    report = await acceptance.verify(database)
    assert report["status"] == "passed"
