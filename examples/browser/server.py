"""MCP tools for one notes web workflow, backed by an owned Playwright browser."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
from typing import Annotated
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field


class Note(BaseModel):
    id: int
    title: str


class Notes(BaseModel):
    notes: list[Note]
    reloaded: bool


class Created(BaseModel):
    note: Note
    confirmed_in_page: bool


Title = Annotated[str, Field(min_length=1, max_length=120, strict=True)]
REQUEST_TIMEOUT_SECONDS = 30


def validate_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise ValueError("Use a fixed HTTP(S) application URL without credentials or fragment")
    return url


class BrowserBridge:
    def __init__(self, url: str, node: str, browser: Path):
        self.url = validate_url(url)
        self.node = str(Path(node).resolve(strict=True))
        self.browser = str(browser.resolve(strict=True))
        self.process = None
        self._starting = None
        self._unusable = False
        self.last_returncode = None
        self.lock = asyncio.Lock()
        self.sequence = 0

    async def _start(self):
        if self._unusable:
            raise RuntimeError("Previous browser worker cleanup failed; close the adapter before continuing")
        if self.process is not None:
            if self.process.returncode is not None:
                await self._stop()
            else:
                return
        env = dict(os.environ)
        env.update(BROWSER_MCP_URL=self.url, BROWSER_MCP_EXECUTABLE=self.browser)
        # Preserve the spawn task on cancellation so cleanup can acquire its handle.
        self._starting = asyncio.create_task(asyncio.create_subprocess_exec(
            self.node, str(Path(__file__).with_name("worker.mjs")),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env, limit=65536,
            **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
               if os.name == "nt" else {"start_new_session": True}),
        ))
        self.process = await asyncio.shield(self._starting)
        self._starting = None

    async def _request(self, operation: str, arguments: dict | None = None):
        await self._start()
        self.sequence += 1
        request = {"id": self.sequence, "operation": operation, "arguments": arguments or {}}
        self.process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode())
        await self.process.stdin.drain()
        line = await asyncio.wait_for(self.process.stdout.readline(), timeout=REQUEST_TIMEOUT_SECONDS)
        if not line:
            raise RuntimeError("Browser worker unavailable; check Node, Playwright and browser configuration")
        try:
            data = json.loads(line)
        except (ValueError, UnicodeError):
            raise RuntimeError("Browser worker returned invalid JSON; inspect state before retrying a write") from None
        if not isinstance(data, dict) or data.get("id") != self.sequence:
            raise RuntimeError("Browser worker response mismatch; inspect state before retrying a write")
        if "error" in data:
            raise RuntimeError(data["error"])
        if "result" not in data:
            raise RuntimeError("Browser worker response has no result")
        return data["result"]

    async def call(self, operation: str, arguments: dict | None = None):
        async with self.lock:
            try:
                return await self._request(operation, arguments)
            except asyncio.CancelledError:
                # An action may have committed even though its response was cancelled.
                # Drain no further responses: retire this session without replaying it.
                await self._retire()
                raise
            except Exception as error:
                if await self._retire():
                    raise asyncio.CancelledError from None
                if isinstance(error, asyncio.TimeoutError):
                    raise RuntimeError("Browser timed out; write outcome unknown; inspect notes before retrying") from None
                raise

    async def _retire(self) -> bool:
        """Finish owned-process cleanup even if the caller cancels again."""
        self._unusable = True
        cleanup = asyncio.create_task(self._stop())
        interrupted = False
        while True:
            try:
                await asyncio.shield(cleanup)
                return interrupted
            except asyncio.CancelledError:
                interrupted = True
                if cleanup.done():
                    cleanup.result()
                    return interrupted

    async def _stop(self):
        self._unusable = True
        if self._starting is not None:
            try:
                self.process = await self._starting
            except Exception:
                # A failed spawn has no process handle to retire.
                if self.process is None:
                    self._unusable = False
                    return
                raise
            finally:
                self._starting = None
        process = self.process
        if process is None:
            self._unusable = False
            return
        if process.returncode is None:
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                if os.name == "nt":
                    killer = await asyncio.create_subprocess_exec(
                        "taskkill", "/PID", str(process.pid), "/T", "/F",
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(killer.wait(), timeout=5)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                await asyncio.wait_for(process.wait(), timeout=5)
        # Discard only once exit has been observed. Retain the handle on failure.
        self.last_returncode = process.returncode
        self.process = None
        self._unusable = False

    async def close(self):
        async with self.lock:
            if self.process is None and self._starting is None:
                return
            failure = None
            try:
                if not self._unusable and self.process is not None and self.process.returncode is None:
                    await self._request("shutdown")
            except BaseException as error:
                failure = error
            interrupted = await self._retire()
            if failure is not None:
                raise failure
            if interrupted:
                raise asyncio.CancelledError


def make_server(bridge: BrowserBridge) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield {}
        finally:
            await bridge.close()

    mcp = FastMCP("Notes browser example", lifespan=lifespan)

    @mcp.tool()
    async def list_notes() -> Notes:
        """Reload the configured notes application and return up to 100 saved notes."""
        return Notes.model_validate(await bridge.call("list_notes"))

    @mcp.tool()
    async def create_note(title: Title) -> Created:
        """Create one note through the page and read back the new note; retries may duplicate it."""
        if title.strip() != title or not title.strip() or not title.isprintable():
            raise ValueError("Title must be printable, nonblank and without outer whitespace")
        return Created.model_validate(await bridge.call("create_note", {"title": title}))

    return mcp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    args = parser.parse_args()
    make_server(BrowserBridge(args.url, str(args.node), args.browser)).run()


if __name__ == "__main__":
    main()
