"""MCP stdio and Streamable HTTP entrypoints; engine output is isolated."""

from __future__ import annotations

import argparse
import os
import re
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .core import Config, Jobs

mcp = FastMCP(
    "LAMMPS MCP",
    instructions=(
        "Probe LAMMPS first. lammps_run_lj submits a bounded reduced-unit demo, not a polymer Tg prediction. "
        "All submissions return a job_id immediately; poll job_status then job_result. "
        "Custom scripts require an operator opt-in and execute with the worker account's privileges. "
        "An exit code of zero does not establish scientific convergence."
    ),
)
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


@lru_cache(maxsize=1)
def jobs() -> Jobs:
    return Jobs(Config.from_env())


@mcp.tool(annotations=READ)
def lammps_probe() -> dict[str, Any]:
    """Check the installed engine and report version, backend and active limits."""
    return jobs().probe()


@mcp.tool(annotations=WRITE)
def lammps_run_lj(
    cells: Annotated[int, Field(strict=True, ge=2, le=8)] = 4,
    steps: Annotated[int, Field(strict=True, ge=0, le=200000)] = 100,
    temperature: Annotated[float, Field(strict=True, ge=0.01, le=10)] = 1.0,
    density: Annotated[float, Field(strict=True, ge=0.1, le=1.5)] = 0.8442,
    timestep: Annotated[float, Field(strict=True, ge=0.0001, le=0.01)] = 0.005,
    seed: Annotated[int, Field(strict=True, ge=1, le=900000000)] = 87287,
    timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=86400)] = 60,
) -> dict[str, Any]:
    """Submit an FCC Lennard-Jones demo in reduced LJ units; cells 2..8, steps 0..200000."""
    return jobs().run_lj(cells, steps, temperature, density, timestep, seed, timeout_seconds)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)
)
def lammps_submit(
    input_script: str,
    files: dict[str, str] | None = None,
    timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=86400)] = 900,
) -> dict[str, Any]:
    """Submit a trusted LAMMPS script and optional flat text files. Disabled unless LAMMPS_ALLOW_TRUSTED_INPUT=1; NOT sandboxed."""
    return jobs().submit(input_script, files, timeout_seconds)


@mcp.tool(annotations=READ)
def job_status(job_id: str) -> dict[str, Any]:
    """Read durable job status. A stale worker is not considered successful."""
    return jobs().status(job_id)


@mcp.tool(annotations=READ)
def job_result(job_id: str) -> dict[str, Any]:
    """Get final status, input hashes, engine version, thermo summary and bounded log tails."""
    return jobs().result(job_id)


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
def job_cancel(job_id: str) -> dict[str, Any]:
    """Request cancellation; the independent worker terminates its engine process tree."""
    return jobs().cancel(job_id)


@mcp.tool(annotations=READ)
def artifact_read(
    job_id: str,
    name: str,
    offset: Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)] = 0,
    max_bytes: Annotated[int, Field(strict=True, ge=1, le=65536)] = 16384,
) -> dict[str, Any]:
    """Read a plain job artifact filename with byte pagination; at most 65536 bytes per call."""
    return jobs().read_artifact(job_id, name, offset, max_bytes)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    """Report service readiness without running or loading the scientific engine."""
    service = jobs()
    return JSONResponse(
        {
            "status": "ok",
            "service": "lammps-mcp",
            "version": __version__,
            "mcp_path": mcp.settings.streamable_http_path,
            "trusted_input_enabled": service.config.allow_trusted,
            "supervisor_required": service.config.use_supervisor,
            "supervisor_ready": service.supervisor_ready(),
        }
    )


@mcp.custom_route("/", methods=["GET"])
async def service_info(_request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "service": "lammps-mcp",
            "version": __version__,
            "transport": "streamable-http",
            "mcp_path": mcp.settings.streamable_http_path,
            "health_path": "/health",
            "usage": "Connect an MCP client to mcp_path; ordinary browser GET is not a tool call.",
        }
    )


def exact_hosts(port: int) -> list[str]:
    """Allow exact authorities, retaining DNS rebinding protection behind a proxy."""
    hosts = [f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"]
    for value in os.environ.get("LAMMPS_MCP_ALLOWED_HOSTS", "").split(","):
        value = value.strip()
        if not value:
            continue
        parsed = urlsplit("//" + value)
        try:
            _ = parsed.port
        except ValueError as error:
            raise ValueError("LAMMPS_MCP_ALLOWED_HOSTS contains an invalid port") from error
        if (
            "*" in value
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"[A-Za-z0-9.\[\]:_-]+", value)
        ):
            raise ValueError("LAMMPS_MCP_ALLOWED_HOSTS must contain exact host[:port] values, without wildcards")
        hosts.append(value)
    return list(dict.fromkeys(hosts))


def exact_origins(port: int) -> list[str]:
    origins = [f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://[::1]:{port}"]
    for value in os.environ.get("LAMMPS_MCP_ALLOWED_ORIGINS", "").split(","):
        value = value.strip()
        if not value:
            continue
        parsed = urlsplit(value)
        try:
            _ = parsed.port
        except ValueError as error:
            raise ValueError("LAMMPS_MCP_ALLOWED_ORIGINS contains an invalid port") from error
        if (
            "*" in value
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "LAMMPS_MCP_ALLOWED_ORIGINS must contain exact HTTP(S) origins, without paths or wildcards"
            )
        origins.append(value)
    return list(dict.fromkeys(origins))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP listening address; use 0.0.0.0 for a platform service"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--path", default="/mcp", help="Streamable HTTP MCP path")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+", args.path) or args.path == "/health":
        parser.error("path must be a nonempty absolute URL path such as /mcp; / and /health are reserved")
    service = jobs()  # Fail early on missing operator workspace configuration.
    if args.transport == "streamable-http":
        if service.config.allow_trusted:
            parser.error(
                "Shared HTTP mode requires LAMMPS_ALLOW_TRUSTED_INPUT=0; trusted scripts use the local stdio service"
            )
        try:
            security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=exact_hosts(args.port),
                allowed_origins=exact_origins(args.port),
            )
        except ValueError as error:
            parser.error(str(error))
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = args.path
        mcp.settings.stateless_http = True
        mcp.settings.json_response = True
        mcp.settings.transport_security = security
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
