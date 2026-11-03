"""Run a real Excel workflow over MCP; only disposable workbooks are used."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def available() -> bool:
    if os.name != "nt" or not shutil.which("pwsh.exe"):
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID"):
            return True
    except OSError:
        return False


async def verify(workspace: Path) -> dict:
    parameters = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("server.py")), "--workspace", str(workspace)])
    async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        names = {tool.name for tool in (await session.list_tools()).tools}
        assert names == {"create_workbook", "read_cells", "write_cells_copy"}
        calls = []
        async def call(tool: str, arguments: dict) -> dict:
            result = await session.call_tool(tool, arguments)
            assert not result.isError, result.content
            output = result.structuredContent
            assert output is not None and output["owned_process_closed"]
            calls.append({"tool": tool, "input": arguments, "output": output})
            return output
        original_values = [["material", "density", "note"], ["copper", 8.96, "=1+1"], ["aluminium", 2.7, True]]
        created = await call("create_workbook", {"output": "sample.xlsx", "values": original_values})
        original_hash = hashlib.sha256((workspace / "sample.xlsx").read_bytes()).hexdigest()
        assert created["sha256"] == original_hash
        read = await call("read_cells", {"workbook": "sample.xlsx", "address": "A1:C3"})
        assert read["values"] == original_values
        updated = await call("write_cells_copy", {"workbook": "sample.xlsx", "output": "updated.xlsx", "start_cell": "B2", "values": [[9.1]]})
        assert updated["sha256"] != original_hash
        reread = await call("read_cells", {"workbook": "updated.xlsx", "address": "B2:C2"})
        assert reread["values"] == [[9.1, "=1+1"]]
        rejected = []
        for tool, arguments in [
            ("create_workbook", {"output": "sample.xlsx", "values": [["overwrite"]]}),
            ("read_cells", {"workbook": "../sample.xlsx", "address": "A1"}),
            ("read_cells", {"workbook": "sample.xlsx", "address": "A1:Z1000"}),
            ("write_cells_copy", {"workbook": "sample.xlsx", "output": "new.xlsx", "start_cell": "A1", "values": [[1], [2, 3]]}),
        ]:
            result = await session.call_tool(tool, arguments)
            assert result.isError
            rejected.append({"tool": tool, "input": arguments})
        assert hashlib.sha256((workspace / "sample.xlsx").read_bytes()).hexdigest() == original_hash
    return {
        "status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "real installed Microsoft Excel COM operations through MCP stdio; no mocks or source checkout",
        "platform": platform.system(), "python": platform.python_version(), "mcp_sdk": version("mcp"),
        "excel_version": created["excel_version"], "tools": sorted(names), "calls": calls,
        "rejected_inputs": rejected, "source_hash_unchanged": True, "formula_like_input_stored_as_literal": True,
        "owned_process_cleanup_confirmed_each_call": True,
        "not_tested": ["Other Office versions", "Untrusted workbooks", "Concurrent external workspace writers", "Formula or macro workbooks", "Remote HTTP deployment"],
        "unsupported": ["PDF export is not exposed. A development probe failed on this host's print-layout backend and then timed out; the recorded owned process was closed. No printer configuration was changed."],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not available():
        parser.error("Windows, PowerShell 7 on PATH and registered Microsoft Excel are required; no execution was performed")
    with tempfile.TemporaryDirectory(prefix="excel-mcp-verify-") as temporary:
        report = asyncio.run(verify(Path(temporary)))
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
        print("Real Excel MCP verification passed; evidence saved.")
    else:
        print(text)


if __name__ == "__main__":
    main()
