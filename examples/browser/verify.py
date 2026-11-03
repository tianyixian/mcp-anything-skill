"""Run real MCP -> Playwright -> notes-page acceptance in a disposable local app."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from demo_app import make_server
from server import BrowserBridge


async def verify(node: Path, browser: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="mcp-browser-check-") as temporary:
        app = make_server(Path(temporary))
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[str(Path(__file__).with_name("server.py")), "--url", app.origin,
                      "--node", str(node), "--browser", str(browser)],
                env={**os.environ},
            )
            async with stdio_client(parameters) as (reader, writer), ClientSession(reader, writer) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert {tool.name for tool in tools} == {"list_notes", "create_note"}
                assert all(tool.outputSchema for tool in tools)
                initial = await session.call_tool("list_notes", {})
                assert not initial.isError and initial.structuredContent == {"notes": [], "reloaded": True}
                created = await session.call_tool("create_note", {"title": "科研验收 note"})
                expected = {"id": 1, "title": "科研验收 note"}
                assert not created.isError and created.structuredContent == {
                    "note": expected, "confirmed_in_page": True,
                }
                reloaded = await session.call_tool("list_notes", {})
                assert not reloaded.isError and reloaded.structuredContent == {"notes": [expected], "reloaded": True}
                before = app.store.path.read_bytes()
                rejected = []
                for title in ["", " ", " outer whitespace", "line\nbreak", "x" * 121, 123]:
                    result = await session.call_tool("create_note", {"title": title})
                    assert result.isError, title
                    rejected.append({"kind": type(title).__name__, "length": len(title) if isinstance(title, str) else None})
                after_rejection = await session.call_tool("list_notes", {})
                assert after_rejection.structuredContent == reloaded.structuredContent
                assert app.store.path.read_bytes() == before
            # A new worker/browser session reads the saved document through the UI.
            bridge = BrowserBridge(app.origin, str(node), browser)
            try:
                reopened = await bridge.call("list_notes")
                assert reopened == {"notes": [expected], "reloaded": True}
                runtime = await bridge.call("runtime")
            finally:
                await bridge.close()
            assert bridge.process is None and bridge.last_returncode == 0
            # Reject an invalid raw application request too, proving persistent state is unchanged.
            request = Request(app.origin + "/api/notes", data=b'{"title":123}', method="POST",
                              headers={"Content-Type": "application/json", "Origin": app.origin})
            try:
                urlopen(request, timeout=5)
                raise AssertionError("Invalid application request unexpectedly succeeded")
            except HTTPError as error:
                assert error.code == 400
            assert app.store.path.read_bytes() == before
            assert json.loads(before) == [expected]
            return {
                "status": "passed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "kind": "real MCP stdio and owned headless browser against a disposable local notes application",
                "platform": platform.system(), "python": platform.python_version(), "mcp_sdk": version("mcp"),
                "runtime": runtime, "tools": [tool.name for tool in tools],
                "calls": [{"tool": "list_notes", "output": initial.structuredContent},
                          {"tool": "create_note", "input": {"title": expected["title"]}, "output": created.structuredContent},
                          {"tool": "list_notes", "output": reloaded.structuredContent}],
                "rejected_inputs": rejected, "invalid_application_request_rejected": True,
                "rejected_requests_preserve_store": True, "new_browser_reads_persisted_note": True,
                "owned_worker_graceful_exit": bridge.last_returncode,
                "not_tested": ["Third-party websites", "Personal authentication/login recovery", "Desktop UI automation",
                               "Site version changes", "Concurrent external writers", "Forced host termination"],
            }
        finally:
            app.shutdown()
            app.server_close()
            thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(verify(args.node.resolve(strict=True), args.browser.resolve(strict=True)))
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        print(f"Browser MCP acceptance passed; report: {args.output.name}")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
