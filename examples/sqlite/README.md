# SQLite → MCP, with a real local example

Let an agent discover ordinary tables, inspect columns, and preview rows from one
operator-selected SQLite database. No database server, cloud account, LAMMPS
installation, or model API key is needed. The adapter was built using the
`mcp-anything` skill as an independent second-interface check.

The code is a small working example, suitable for local inspection of trusted
database files. It exposes three named operations rather than an SQL executor.

## Try it

Use Python 3.11 or newer with SQLite 3.37 or newer. SQLite is included with Python;
its version can be checked with `python -c "import sqlite3; print(sqlite3.sqlite_version)"`.
From the repository root, in your virtual environment:

```sh
python -m pip install "mcp>=1.26,<2"
python examples/sqlite/make_sample.py examples/sqlite/sample.sqlite
python examples/sqlite/verify.py
```

The sample utility creates two tables with four illustrative rows and refuses
to overwrite an existing file. `verify.py` creates its own temporary sample,
starts the actual MCP process, calls all three tools, checks known values,
rejects invalid requests, and verifies that the database file did not change.
Its JSON output includes the Python, SQLite, and MCP SDK versions.

To connect from a client supporting the common `mcpServers` configuration, use
absolute paths to your virtual environment's Python, this script, and the sample:

```json
{
  "mcpServers": {
    "sqlite-preview": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": [
        "/absolute/path/to/mcp-anything-skill/examples/sqlite/server.py",
        "--database",
        "/absolute/path/to/sample.sqlite"
      ]
    }
  }
}
```

On Windows, use the environment's `Scripts/python.exe`; forward slashes work in
JSON paths. In Codex, place the same `command` and `args` values under
`[mcp_servers.sqlite-preview]` in the TOML client configuration.

Ask the agent: “List the database tables, inspect `materials`, then preview two rows.”
The exact tool calls and recovery instructions are in [USAGE.md](USAGE.md).

## Contract and limits

| Operation | Inputs | Result |
| --- | --- | --- |
| `list_tables` | `limit`: 1–100, default 20; `after`: table name, default empty | Ordered ordinary-table names and `next_after` cursor |
| `describe_table` | `table`: exact name returned by discovery | Columns, declared types, declared NOT NULL flags, primary-key positions, SQLite version |
| `preview_rows` | `table`; `limit`: 1–50, default 10 | Column names, row arrays, truncation metadata |

The database path is startup configuration; callers cannot change it. SQLite opens
the file with `mode=ro`, also enables `query_only`, and disables trusted schema
features. Views, virtual/shadow tables and SQLite internal tables are excluded.
No arbitrary SQL, writes, attachments, or extension loading is exposed.

- Main database file: at most **64 MiB**. Use a small, stable snapshot; this is
  not a bound on existing journal/WAL files or OS filesystem caches.
- Supported table: at most **64 columns**. Table/column names are limited to
  **128 UTF-8 bytes** by discovery/inspection. Declared type text is abbreviated
  to 128 characters. Hidden/generated columns are omitted by `table_info`.
- Rows: at most **50** per call, without a guaranteed order. Row previews have
  no pagination or filtering and are not suitable for an exhaustive export.
- Structured result: at most **32 KiB**, measured as compact UTF-8 JSON. MCP
  framing and the SDK's text representation add protocol overhead.
- Text values: at most **2 KiB** of UTF-8; `value_truncations` counts clipped
  text/blob cells. Blobs return their byte length and the first 32 bytes as hex.
- SQLite value/row length: **256 KiB**; oversized rows may be rejected even when
  the intended preview is small. This prevents loading arbitrarily large cells.
- SQL VM deadline: **1 second**, checked every 1,000 VM instructions; lock wait:
  **0.1 second**. These are bounded-query controls, not a hard process wall-clock
  or memory sandbox. Filesystem I/O and SQLite parsing may delay interruption.

Read-only mode prevents writes through this adapter; it does not make malicious
database files safe or hide sensitive rows. Only connect files that the caller
is allowed to read. This example has no remote transport or user authentication.

## Reproduce the checks

Using the repository's development dependencies:

```sh
python -m pytest examples/sqlite -q
python examples/sqlite/verify.py --output docs/sqlite-validation.json
```

The tests exercise real SQLite write rejection, safe quoted names, view rejection,
text/blob/output limits, oversized cells, actual SQLite progress interruption,
and a separate MCP stdio process. The checked-in [acceptance record](../../docs/sqlite-validation.json)
records the environment where it actually ran; a CI configuration alone is not a
passed run on another platform.

## Source and license

The adapter and sample are original code under the repository's MIT license.
It uses Python's documented [`sqlite3`](https://docs.python.org/3/library/sqlite3.html)
interface, SQLite's [`mode=ro` URI option](https://sqlite.org/uri.html),
[`table_list` / `table_info` pragmas](https://sqlite.org/pragma.html), and the MCP
Python SDK. SQLite is [public domain](https://sqlite.org/copyright.html);
Python and the MCP SDK retain their own licenses. No upstream engine source or
third-party database is bundled. This example's provenance is the runtime
versions in the acceptance record, rather than a claimed upstream Git commit.
