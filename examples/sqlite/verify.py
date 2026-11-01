"""Exercise a real SQLite database through a separate MCP stdio process."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from make_sample import make_sample


async def verify(database: Path) -> dict:
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("server.py")), "--database", str(database)],
    )
    async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        assert {tool.name for tool in tools} == {"list_tables", "describe_table", "preview_rows"}
        assert all(tool.outputSchema for tool in tools)
        calls = []
        for name, arguments in [
            ("list_tables", {"limit": 1}),
            ("list_tables", {"after": "materials", "limit": 1}),
            ("describe_table", {"table": "materials"}),
            ("preview_rows", {"table": "materials", "limit": 2}),
        ]:
            result = await session.call_tool(name, arguments)
            assert not result.isError, result.content
            assert result.structuredContent is not None
            calls.append({"tool": name, "input": arguments, "output": result.structuredContent})
        assert calls[0]["output"] == {"tables": ["materials"], "next_after": "materials"}
        assert calls[1]["output"] == {"tables": ["notes"], "next_after": None}
        assert [column["name"] for column in calls[2]["output"]["columns"]] == ["id", "name", "density"]
        assert calls[3]["output"]["rows"] == [[1, "aluminium", 2.7], [2, "copper", 8.96]]
        assert calls[3]["output"]["truncation_reason"] == "row_limit"
        rejected = []
        for arguments in [
            {"table": "materials", "limit": 51},
            {"table": "materials", "limit": True},
            {"table": "materials; DROP TABLE notes;--"},
            {"table": "sqlite_schema"},
        ]:
            result = await session.call_tool("preview_rows", arguments)
            assert result.isError
            rejected.append(arguments)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == digest
    return {
        "status": "passed",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "real SQLite operations over MCP stdio, not mocked",
        "platform": platform.system(), "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version, "mcp_sdk": version("mcp"),
        "tools": [tool.name for tool in tools], "structured_schemas": True,
        "calls": calls, "rejected_inputs": rejected, "database_hash_unchanged": True,
        "limits": {"rows": 50, "structured_result_bytes": 32768, "database_bytes": 67108864,
                   "text_value_bytes": 2048, "query_progress_deadline_seconds": 1.0},
        "not_tested": ["Remote HTTP deployment", "Concurrent database writers", "Adversarial SQLite files"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sqlite-mcp-check-") as temporary:
        database = Path(temporary) / "sample.sqlite"
        make_sample(database)
        report = asyncio.run(verify(database))
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        print(f"SQLite MCP acceptance passed; report: {args.output.name}")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
