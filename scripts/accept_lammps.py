"""Require real LAMMPS execution through an installed MCP server, including reconnect."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def payload(result):
    if result.isError:
        raise RuntimeError(str(result.content))
    return result.structuredContent or json.loads(result.content[0].text)


@asynccontextmanager
async def connect(params):
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as client:
            await client.initialize()
            yield client


async def terminal(client, job_id, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = payload(await client.call_tool("job_status", {"job_id": job_id}))
        if state["status"] not in {"queued", "running"}:
            return payload(await client.call_tool("job_result", {"job_id": job_id}))
        await asyncio.sleep(0.25)
    raise TimeoutError("Acceptance job did not finish")


async def accept(args):
    workspace = args.workspace.resolve()
    env = {**os.environ, "LAMMPS_MCP_WORKSPACE": str(workspace), "LAMMPS_ALLOW_TRUSTED_INPUT": "0"}
    env["LAMMPS_USE_SUPERVISOR"] = "1"
    env.pop("LAMMPS_EXECUTABLE", None)
    if args.executable:
        env["LAMMPS_EXECUTABLE"] = str(args.executable.resolve())
    params = StdioServerParameters(command=str(args.python.resolve()), args=["-m", "lammps_mcp"], env=env)
    async with connect(params) as client:
        tools = await client.list_tools()
        assert len(tools.tools) == 7
        probe = payload(await client.call_tool("lammps_probe", {}))
        assert probe["available"], probe
        invalid = await client.call_tool("lammps_run_lj", {"cells": 999})
        disabled = await client.call_tool("lammps_submit", {"input_script": "print test"})
        assert invalid.isError and disabled.isError
        submitted = payload(await client.call_tool("lammps_run_lj", {"cells": 4, "steps": 100, "timeout_seconds": 60}))
        result = await terminal(client, submitted["job_id"])
        assert result["status"] == "succeeded", result
        assert result["summary"]["created_atoms"] == 256
        assert result["summary"]["last"]["Step"] == 100
        stdout = payload(await client.call_tool("artifact_read", {"job_id": submitted["job_id"], "name": "stdout.txt", "max_bytes": 65536}))
        assert "Total wall time" in stdout["text"]
        restart_job = payload(await client.call_tool("lammps_run_lj", {"cells": 8, "steps": 5000, "timeout_seconds": 60}))
        for _ in range(100):
            before = payload(await client.call_tool("job_status", {"job_id": restart_job["job_id"]}))
            if before["status"] == "running" and before.get("engine_pid"):
                break
            await asyncio.sleep(0.05)
        assert before["status"] == "running" and before.get("engine_pid"), before
    # The client context closes the first MCP server while its engine is running.
    async with connect(params) as client:
        after = await terminal(client, restart_job["job_id"])
        assert after["status"] == "succeeded", after
        assert after["summary"]["last"]["Step"] == 5000
        assert after["summary"]["created_atoms"] == 2048
    evidence = {
        "schema_version": 1,
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "backend": probe["backend"],
        "supervisor_started_outside_mcp": True,
        "tool_count": len(tools.tools),
        "tools": sorted(t.name for t in tools.tools),
        "structured_output_schemas": all(t.outputSchema is not None for t in tools.tools),
        "small_run": {"status": result["status"], "engine": result["engine"], "input_sha256": result["input_sha256"], "summary": result["summary"]},
        "restart_run": {"observed_running_before_disconnect": True, "status": after["status"], "atoms": after["summary"]["created_atoms"], "final_step": after["summary"]["last"]["Step"]},
        "invalid_numeric_input_rejected": invalid.isError,
        "trusted_input_disabled_by_default": disabled.isError,
        "scope": "Real local CPU engine, stdio transport; no polymer Tg or cluster validation."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    # A sibling of the MCP client transport, never a child of the MCP server.
    launched_at = time.time()
    supervisor = subprocess.Popen([str(args.python.resolve()), "-m", "lammps_mcp.supervisor", "--workspace", str(workspace)],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, **options)
    try:
        for _ in range(100):
            if supervisor.poll() is not None:
                raise RuntimeError("Independent supervisor failed to start")
            try:
                heartbeat = json.loads((workspace / ".supervisor.json").read_text())
                # A Windows venv launcher may have a different PID from its interpreter.
                if heartbeat["heartbeat_at"] >= launched_at and time.time() - heartbeat["heartbeat_at"] < 5:
                    break
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.05)
        else:
            raise TimeoutError("Independent supervisor did not become ready")
        asyncio.run(accept(args))
    finally:
        if os.name == "nt" and supervisor.poll() is None:
            subprocess.run(["taskkill.exe", "/PID", str(supervisor.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        elif supervisor.poll() is None:
            supervisor.terminate()
        supervisor.wait(timeout=10)


if __name__ == "__main__":
    main()
