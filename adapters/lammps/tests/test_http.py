"""Real HTTP protocol checks; engine integration is labeled separately."""

import asyncio
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from lammps_mcp.server import exact_hosts, exact_origins


def stop_process(process):
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            process.terminate()
        process.wait(timeout=10)


@pytest.fixture
def http_service(tmp_path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {
        **os.environ,
        "LAMMPS_MCP_WORKSPACE": str(tmp_path),
        "LAMMPS_ALLOW_TRUSTED_INPUT": "0",
        "LAMMPS_USE_SUPERVISOR": "1",
        "LAMMPS_MCP_ALLOWED_HOSTS": "lammps.qz.example",
        "LAMMPS_MCP_ALLOWED_ORIGINS": "https://qz.example",
    }
    env.pop("LAMMPS_EXECUTABLE", None)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    supervisor = subprocess.Popen(
        [sys.executable, "-m", "lammps_mcp.supervisor", "--workspace", str(tmp_path)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **options,
    )
    log = (tmp_path / "http-server.log").open("w+", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lammps_mcp",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--path",
            "/tools/mcp",
        ],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        **options,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(trust_env=False, timeout=0.5) as client:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if server.poll() is not None or supervisor.poll() is not None:
                    log.seek(0)
                    pytest.fail("HTTP or supervisor failed to start: " + log.read())
                try:
                    response = client.get(base_url + "/health")
                    if response.status_code == 200 and response.json()["supervisor_ready"]:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                log.seek(0)
                pytest.fail("HTTP readiness timeout: " + log.read())
        yield base_url
    finally:
        stop_process(server)
        stop_process(supervisor)
        log.close()


def test_http_health_and_proxy_host_validation(http_service):
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "host-test", "version": "1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    with httpx.Client(trust_env=False) as client:
        health = client.get(http_service + "/health")
        assert health.status_code == 200
        assert health.json()["mcp_path"] == "/tools/mcp"
        assert health.json()["trusted_input_enabled"] is False
        assert client.get(http_service + "/").json()["transport"] == "streamable-http"
        denied = client.post(
            http_service + "/tools/mcp", json=initialize, headers={**headers, "Host": "unlisted.example"}
        )
        assert denied.status_code == 421
        allowed = client.post(
            http_service + "/tools/mcp",
            json=initialize,
            headers={**headers, "Host": "lammps.qz.example", "Origin": "https://qz.example"},
        )
        assert allowed.status_code == 200
        forbidden_origin = client.post(
            http_service + "/tools/mcp", json=initialize, headers={**headers, "Origin": "https://unlisted.example"}
        )
        assert forbidden_origin.status_code == 403


@pytest.mark.asyncio
async def test_http_mcp_handshake_probe_and_disabled_input(http_service):
    async with (
        httpx.AsyncClient(trust_env=False, timeout=30) as http_client,
        streamable_http_client(http_service + "/tools/mcp", http_client=http_client) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert len(tools.tools) == 7
        probe = await session.call_tool("lammps_probe", {})
        assert not probe.isError
        assert isinstance(probe.structuredContent["available"], bool)
        assert probe.structuredContent["trusted_input_enabled"] is False
        invalid = await session.call_tool("lammps_run_lj", {"cells": 100})
        assert invalid.isError
        trusted = await session.call_tool("lammps_submit", {"input_script": "print test"})
        assert trusted.isError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_lj_through_streamable_http(http_service):
    async with (
        httpx.AsyncClient(trust_env=False, timeout=30) as http_client,
        streamable_http_client(http_service + "/tools/mcp", http_client=http_client) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        probe = await session.call_tool("lammps_probe", {})
        if not probe.structuredContent["available"]:
            pytest.skip("Real LAMMPS engine unavailable")
        submitted = await session.call_tool("lammps_run_lj", {"cells": 4, "steps": 100})
        assert not submitted.isError
        job_id = submitted.structuredContent["job_id"]
        for _ in range(300):
            state = await session.call_tool("job_status", {"job_id": job_id})
            assert not state.isError
            if state.structuredContent["status"] not in {"queued", "running"}:
                break
            await asyncio.sleep(0.1)
        result = await session.call_tool("job_result", {"job_id": job_id})
        assert not result.isError
        assert result.structuredContent["status"] == "succeeded"
        assert result.structuredContent["summary"]["created_atoms"] == 256
        assert result.structuredContent["summary"]["last"]["Step"] == 100


def test_http_mode_refuses_trusted_scripts(tmp_path):
    process = subprocess.run(
        [sys.executable, "-m", "lammps_mcp", "--transport", "streamable-http"],
        env={**os.environ, "LAMMPS_MCP_WORKSPACE": str(tmp_path), "LAMMPS_ALLOW_TRUSTED_INPUT": "1"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 2
    assert "Shared HTTP mode requires" in process.stderr


def test_proxy_allowlists_require_exact_values(monkeypatch):
    monkeypatch.setenv("LAMMPS_MCP_ALLOWED_HOSTS", "*.example")
    with pytest.raises(ValueError, match="exact"):
        exact_hosts(8765)
    monkeypatch.setenv("LAMMPS_MCP_ALLOWED_ORIGINS", "https://example/path")
    with pytest.raises(ValueError, match="exact"):
        exact_origins(8765)
