import asyncio
import json
import os
import subprocess
import sys
import time

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from lammps_mcp.core import Config, Jobs


def payload(result):
    assert not result.isError, result.content
    if result.structuredContent:
        return result.structuredContent
    return json.loads(result.content[0].text)


@pytest.fixture
def supervisor(tmp_path):
    process = subprocess.Popen(
        [sys.executable, "-m", "lammps_mcp.supervisor", "--workspace", str(tmp_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        service = Jobs(Config(tmp_path))
        deadline = time.monotonic() + 10
        while not service.supervisor_ready():
            if process.poll() is not None:
                pytest.fail(process.stderr.read().decode())
            if time.monotonic() >= deadline:
                pytest.fail("Supervisor did not initialize")
            time.sleep(0.05)
        yield process
    finally:
        process.terminate()
        process.wait(timeout=5)
        process.stderr.close()


def test_only_one_supervisor_per_workspace(tmp_path, supervisor):
    duplicate = subprocess.run(
        [sys.executable, "-m", "lammps_mcp.supervisor", "--workspace", str(tmp_path)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert duplicate.returncode != 0
    assert supervisor.poll() is None


@pytest.mark.asyncio
async def test_mcp_handshake_tools_and_validation(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lammps_mcp"],
        env={**os.environ, "LAMMPS_MCP_WORKSPACE": str(tmp_path), "LAMMPS_ALLOW_TRUSTED_INPUT": "0", "LAMMPS_USE_SUPERVISOR": "1"},
    )
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        listed = await session.list_tools()
        assert {t.name for t in listed.tools} == {
            "lammps_probe",
            "lammps_run_lj",
            "lammps_submit",
            "job_status",
            "job_result",
            "job_cancel",
            "artifact_read",
        }
        rejected = await session.call_tool("lammps_run_lj", {"cells": 999})
        assert rejected.isError
        boolean_value = await session.call_tool("lammps_run_lj", {"steps": True})
        assert boolean_value.isError
        lj_schema = next(tool.inputSchema for tool in listed.tools if tool.name == "lammps_run_lj")
        assert lj_schema["properties"]["cells"]["maximum"] == 8
        trusted = await session.call_tool("lammps_submit", {"input_script": "print hello"})
        assert trusted.isError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_lj_stdio_and_restart(tmp_path, supervisor):
    service = Jobs(Config(tmp_path))
    if not service.probe().get("available"):
        pytest.skip("Real LAMMPS engine unavailable")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "lammps_mcp"],
        env={**os.environ, "LAMMPS_MCP_WORKSPACE": str(tmp_path), "LAMMPS_ALLOW_TRUSTED_INPUT": "0", "LAMMPS_USE_SUPERVISOR": "1"},
    )
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        probe = payload(await session.call_tool("lammps_probe", {}))
        assert probe["available"], probe
        response = await session.call_tool("lammps_run_lj", {"cells": 4, "steps": 100, "timeout_seconds": 60})
        assert not response.isError
        submitted = payload(response)
    # The submitting MCP process has exited. A new server reads the durable worker result.
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        for _ in range(300):
            state = payload(await session.call_tool("job_status", {"job_id": submitted["job_id"]}))
            if state["status"] not in {"queued", "running"}:
                break
            await asyncio.sleep(0.1)
        result = payload(await session.call_tool("job_result", {"job_id": submitted["job_id"]}))
        assert result["status"] == "succeeded", result
        assert result["summary"]["created_atoms"] == 256
        assert result["summary"]["last"]["Step"] == 100
        assert result["engine"]["version"]
        artifact = await session.call_tool(
            "artifact_read", {"job_id": submitted["job_id"], "name": "stdout.txt", "max_bytes": 65536}
        )
        assert not artifact.isError
        assert "Total wall time" in payload(artifact)["text"]
