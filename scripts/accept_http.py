"""Accept a remote LAMMPS MCP service through the official Streamable HTTP client.

Requires Python 3.11+, mcp, and httpx; no local LAMMPS installation is used.
Optional gateway authentication comes from INF_API_KEY, never a command argument.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = {
    "artifact_read", "job_cancel", "job_result", "job_status",
    "lammps_probe", "lammps_run_lj", "lammps_submit",
}


class AcceptanceError(RuntimeError):
    """A diagnostic constructed without server text, URLs, or authentication data."""


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


def public_url(value):
    """Keep the service location but omit URL credentials, query, and fragment."""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    authority = host + (f":{parsed.port}" if parsed.port else "")
    return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))


def payload(result, name):
    require(not result.isError, f"Tool {name} returned an error")
    data = result.structuredContent
    if data is None:
        try:
            data = json.loads(next(item.text for item in result.content if item.type == "text"))
        except (StopIteration, TypeError, ValueError) as error:
            raise AcceptanceError(f"Tool {name} returned no JSON object") from error
    require(isinstance(data, dict), f"Tool {name} returned an unexpected payload")
    return data


async def call(client, name, arguments):
    return payload(await client.call_tool(name, arguments), name)


@asynccontextmanager
async def connect(args):
    key = os.environ.get("INF_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    if args.header_host:
        headers["Host"] = args.header_host
    async with (
        httpx.AsyncClient(headers=headers, timeout=args.request_timeout, trust_env=False) as http_client,
        streamable_http_client(args.url, http_client=http_client) as streams,
        ClientSession(
            streams[0], streams[1],
            read_timeout_seconds=timedelta(seconds=args.request_timeout),
        ) as client,
    ):
        await client.initialize()
        yield client


async def terminal(client, job_id, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        state = await call(client, "job_status", {"job_id": job_id})
        status = state.get("status")
        if status not in {"queued", "running"}:
            require(status == "succeeded", "Computation did not reach succeeded status")
            return await call(client, "job_result", {"job_id": job_id})
        await asyncio.sleep(0.15)
    raise AcceptanceError("Timed out waiting for computation completion")


def validate_result(result, submitted, atoms, steps):
    require(result.get("status") == "succeeded", "Result is not succeeded")
    require(result.get("exit_code") == 0, "Engine exit code is not zero")
    summary = result.get("summary") or {}
    last = summary.get("last") or {}
    require(summary.get("created_atoms") == atoms, "Unexpected created atom count")
    require(last.get("Step") == steps, "Unexpected final simulation timestep")
    require(summary.get("thermo_rows", 0) >= 2, "Missing thermo trajectory")
    require(summary.get("reported_total_wall_time") is True, "Missing engine completion marker")
    require(
        all(isinstance(last.get(key), (int, float)) and math.isfinite(last[key])
            for key in ("Temp", "PotEng", "KinEng", "TotEng", "Press")),
        "Missing or non-finite thermodynamic output",
    )
    engine = result.get("engine") or {}
    require(bool(engine.get("version")) and bool(engine.get("backend")), "Missing real engine provenance")
    hashes = result.get("input_sha256") or {}
    require(bool(re.fullmatch(r"[a-f0-9]{64}", hashes.get("input.in", ""))), "Missing input SHA-256")
    require(hashes == submitted.get("input_sha256"), "Input hashes changed between submission and result")
    return {
        "job_id": submitted["job_id"], "status": result["status"],
        "engine": engine, "input_sha256": hashes, "summary": summary,
    }


async def accept(args, evidence, jobs):
    evidence["stage"] = "connect_and_discover"
    async with connect(args) as client:
        tools = (await client.list_tools()).tools
        names = {tool.name for tool in tools}
        require(len(tools) == 7 and names == EXPECTED_TOOLS, "Expected exactly the seven LAMMPS tools")
        require(all(tool.outputSchema is not None for tool in tools), "Missing structured output schemas")
        evidence.update({"tools": sorted(names), "tool_count": len(tools), "structured_output_schemas": True})

        evidence["stage"] = "probe_real_engine"
        probe = await call(client, "lammps_probe", {})
        require(probe.get("available") is True, "Remote LAMMPS engine is unavailable")
        require(probe.get("trusted_input_enabled") is False, "Shared service allows trusted scripts")
        evidence["probe"] = {"available": True, "backend": probe.get("backend"), "trusted_input_enabled": False}

        evidence["stage"] = "restricted_input_checks"
        invalid = await client.call_tool("lammps_run_lj", {"cells": 999})
        require(invalid.isError is True, "Out-of-range numeric input was accepted")
        disabled = await client.call_tool("lammps_submit", {"input_script": "print test"})
        require(disabled.isError is True, "Trusted script submission was accepted")
        evidence.update({"invalid_numeric_input_rejected": True, "trusted_input_rejected": True})

        evidence["stage"] = "small_computation"
        submitted = await call(client, "lammps_run_lj", {"cells": 4, "steps": 100, "timeout_seconds": 60})
        jobs.append(submitted["job_id"])
        result = await terminal(client, submitted["job_id"], args.job_timeout)
        evidence["small_run"] = validate_result(result, submitted, atoms=256, steps=100)

        evidence["stage"] = "read_computation_artifact"
        stdout = await call(client, "artifact_read", {
            "job_id": submitted["job_id"], "name": "stdout.txt", "offset": 0, "max_bytes": 65536,
        })
        require("Total wall time" in stdout.get("text", ""), "Read artifact lacks engine completion marker")
        evidence["artifact_read"] = {
            "name": "stdout.txt", "total_bytes": stdout.get("total_bytes"),
            "returned_text_sha256": hashlib.sha256(stdout["text"].encode("utf-8")).hexdigest(),
            "contains_engine_completion_marker": True, "truncated": stdout.get("truncated"),
        }

        evidence["stage"] = "observe_running_before_disconnect"
        reconnect_job = await call(client, "lammps_run_lj", {"cells": 8, "steps": 5000, "timeout_seconds": 60})
        jobs.append(reconnect_job["job_id"])
        deadline = time.monotonic() + args.job_timeout
        while time.monotonic() < deadline:
            before = await call(client, "job_status", {"job_id": reconnect_job["job_id"]})
            if before.get("status") == "running" and before.get("engine_pid"):
                break
            require(before.get("status") in {"queued", "running"}, "Job ended before a running engine was observed")
            await asyncio.sleep(0.05)
        else:
            raise AcceptanceError("Timed out waiting for a running engine process")
        evidence["connection_reconnect"] = {
            "job_id": reconnect_job["job_id"], "observed_running_before_disconnect": True,
            "engine_pid_before_disconnect": before["engine_pid"],
            "scope": "HTTP client disconnected and reconnected; server was not restarted",
        }

    # Close both the first MCP session and its HTTP client while the engine is running.
    evidence["stage"] = "new_connection_waits_for_existing_computation"
    async with connect(args) as client:
        result = await terminal(client, reconnect_job["job_id"], args.job_timeout)
        evidence["reconnect_run"] = validate_result(result, reconnect_job, atoms=2048, steps=5000)
        evidence["connection_reconnect"]["new_http_client_and_mcp_session"] = True
    evidence.update({"stage": "complete", "success": True})


async def cancel_owned_jobs(args, jobs):
    """Best effort cleanup only for job IDs submitted by this invocation."""
    if not jobs:
        return "not_needed"
    try:
        async with asyncio.timeout(10), connect(args) as client:
            for job_id in jobs:
                await client.call_tool("job_cancel", {"job_id": job_id})
        return "requested_for_own_jobs_only"
    except Exception:  # noqa: BLE001 - cleanup must preserve the original failure, without leaking diagnostics.
        return "cleanup_unavailable"


def safe_error(error):
    if isinstance(error, AcceptanceError):
        return str(error)
    if isinstance(error, BaseExceptionGroup):
        for child in error.exceptions:
            message = safe_error(child)
            if not message.startswith("Transport or protocol failure"):
                return message
        return "Transport or protocol failure (" + type(error).__name__ + ")"
    if isinstance(error, TimeoutError):
        return "Overall acceptance deadline exceeded"
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP service returned status {error.response.status_code}"
    if isinstance(error, httpx.TimeoutException):
        return "HTTP request timed out"
    if isinstance(error, httpx.RequestError):
        return f"HTTP request failed ({type(error).__name__})"
    return "Transport or protocol failure (" + type(error).__name__ + ")"


async def run(args, evidence):
    jobs = []
    try:
        async with asyncio.timeout(args.overall_timeout):
            await accept(args, evidence, jobs)
        return 0
    except Exception as error:  # noqa: BLE001 - CLI boundary emits sanitized failures instead of tracebacks with URLs.
        evidence.update({"success": False, "error": safe_error(error)})
        evidence["cleanup"] = await cancel_owned_jobs(args, jobs)
        return 1


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Full remote Streamable HTTP MCP endpoint")
    parser.add_argument("--output", type=Path, required=True, help="Evidence JSON path")
    parser.add_argument("--label", required=True, help="Human-readable test location")
    parser.add_argument("--header-host", help="Optional exact proxy Host authority; normally unnecessary")
    parser.add_argument("--request-timeout", type=positive_number, default=30)
    parser.add_argument("--job-timeout", type=positive_number, default=90)
    parser.add_argument("--overall-timeout", type=positive_number, default=240)
    args = parser.parse_args()
    try:
        parsed = urlsplit(args.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("invalid endpoint")
        endpoint = public_url(args.url)
    except ValueError:
        parser.error("--url must be a valid HTTP(S) MCP endpoint")

    # Library diagnostics may contain URLs; report only the sanitized evidence below.
    logging.disable(logging.CRITICAL)
    evidence = {
        "schema_version": 1, "label": args.label, "endpoint": endpoint,
        "started_at": datetime.now(UTC).isoformat(),
        "client_platform": sys.platform, "python": sys.version.split()[0],
        "transport": "streamable-http", "success": False,
        "scope": "Real remote CPU engine; no local engine, polymer Tg, or cluster validation",
    }
    try:
        code = asyncio.run(run(args, evidence))
    except KeyboardInterrupt:
        code = 130
        evidence.update({"success": False, "error": "Interrupted by operator"})
    evidence["finished_at"] = datetime.now(UTC).isoformat()
    serialized = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    secret = os.environ.get("INF_API_KEY", "").strip()
    if secret:
        serialized = serialized.replace(secret, "[REDACTED]")
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    except OSError:
        print("FAIL: could not write acceptance evidence", file=sys.stderr)
        return 1
    if code:
        print(f"FAIL at {evidence.get('stage', 'startup')}: {evidence.get('error', 'unknown failure')}", file=sys.stderr)
    else:
        print("PASS: seven tools; real 256-atom/100-step run; artifact; running 2048-atom/5000-step reconnect")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
