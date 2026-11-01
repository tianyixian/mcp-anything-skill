# LAMMPS MCP

A **stdio or Streamable HTTP MCP server** for durable LAMMPS jobs. Generated using this repository's `mcp-anything` skill, then implemented against LAMMPS `stable_22Jul2025_update4` (commit `611ca3b7f8525ba802373b04f9e3d632d515f7e3`). The engine is installed separately; this project is not an upstream-endorsed product.

The default tool runs a bounded Lennard-Jones demonstration. The trusted-input tool runs supplied LAMMPS scripts after operator opt-in. **Running the demo does not establish validated polymer Tg predictions.** Structures, force fields, cooling protocols and scientific convergence require separate validation.

## Install and configure

Python 3.11+:

Run these commands from this adapter's directory: `adapters/lammps` in the full repository, or the extracted standalone `lammps-mcp` archive root.

```sh
python -m venv .venv
# Activate .venv using your platform's normal command.
python -m pip install '.[engine]'
```

For an existing native LAMMPS installation, omit `[engine]` and set `LAMMPS_EXECUTABLE` to an absolute native executable path. Otherwise the adapter uses the Python LAMMPS library in a separate process. Its OS dependencies remain necessary: the tested Windows wheel requires Microsoft MPI (`msmpi.dll`), installable through Microsoft MPI or the corresponding conda-forge runtime. A successful package installation alone does not prove the engine can initialize. Linux distributions may also require the matching MPI runtime.

**Windows requires an independent supervisor**, started before the MCP client from a separate terminal or OS service:

```sh
python -m lammps_mcp.supervisor --workspace /absolute/path/lammps-jobs
```

Use an absolute Windows path such as `C:/work/lammps-jobs` on Windows. Keep this process running; it starts queued workers outside the MCP client's process tree. Many Windows MCP clients kill the entire server process tree on disconnect, so a detached child of the server alone cannot guarantee persistence. On POSIX the server starts workers in independent sessions; `LAMMPS_USE_SUPERVISOR=1` optionally uses the same supervisor arrangement.

Configure your MCP client:

```json
{
  "mcpServers": {
    "lammps": {
      "command": "/absolute/path/.venv/bin/python",
      "args": ["-m", "lammps_mcp"],
      "env": {"LAMMPS_MCP_WORKSPACE": "/absolute/path/lammps-jobs"}
    }
  }
}
```

On Windows, `command` should be `C:/.../.venv/Scripts/python.exe`. The workspace must be a dedicated directory owned by the service account, without symlinks/junctions. The supervisor and MCP server must use the same installed Python environment and workspace. The default transport is stdio and opens no network listener.

Codex example:

```toml
[mcp_servers.lammps]
command = "/absolute/path/.venv/bin/python"
args = ["-m", "lammps_mcp"]
env = { LAMMPS_MCP_WORKSPACE = "/absolute/path/lammps-jobs" }
```

## Shared platform HTTP service

Version 0.2.0 adds stateless Streamable HTTP for clients connecting by URL. Start it explicitly:

```sh
export LAMMPS_MCP_WORKSPACE=/absolute/path/lammps-jobs
export LAMMPS_ALLOW_TRUSTED_INPUT=0
export LAMMPS_MCP_ALLOWED_HOSTS=service.example.org
export LAMMPS_MCP_ALLOWED_ORIGINS=https://service.example.org
python -m lammps_mcp --transport streamable-http --host 0.0.0.0 --port 8765 --path /mcp
```

Use your deployment's actual proxy hostname in place of `service.example.org`. Configure the platform's normal HTTP routing to this port and give collaborators that platform URL ending in `/mcp`. A `127.0.0.1` URL only works on the service machine and is not a shared deployment URL. This package does not create a gateway, tunnel or platform route itself.

`GET /health` reports process/configuration readiness without starting a calculation. `GET /` shows the service version and endpoint paths. A standard MCP client connects to `/mcp` and performs initialization, tool discovery and tool calls; opening that path in a browser is not a simulation request.

DNS rebinding protection remains enabled. `LAMMPS_MCP_ALLOWED_HOSTS` is a comma-separated list of exact `host[:port]` values accepted from the proxy; wildcards and URLs are rejected. `LAMMPS_MCP_ALLOWED_ORIGINS` accepts exact HTTP(S) origins, without paths. Localhost authorities/origins on the listening port are also accepted for health and protocol tests. These settings validate routing headers; they do not authenticate users.

Shared HTTP mode requires `LAMMPS_ALLOW_TRUSTED_INPUT=0` and refuses startup if trusted scripts are enabled. This deployment exposes the bounded LJ demonstration and job management; it is intended for a platform-controlled collaboration network. Use a dedicated demo workspace with no private research inputs. Jobs are shared across clients, and anyone with a job UUID can read or cancel that job. Per-user authorization and confidential multi-tenant research workspaces are outside this version. Reviewed custom scripts remain available through operator-controlled stdio deployments.

## Tools and workflow

| Tool | Purpose |
|---|---|
| `lammps_probe` | Check engine/version, limits and supervisor readiness. |
| `lammps_run_lj` | Submit a restricted numerical LJ demonstration. |
| `lammps_submit` | Submit a trusted script plus optional flat UTF-8 files; disabled by default. |
| `job_status` | Read durable status and heartbeat. |
| `job_result` | Get final exit status, hashes, engine version, thermo summary and log tails. |
| `job_cancel` | Ask the worker to terminate its engine process tree. |
| `artifact_read` | Read a bounded page of a named artifact. |

```text
lammps_probe {}
lammps_run_lj {"cells":4,"steps":100,"timeout_seconds":60}
job_status {"job_id":"<returned UUID>"}
job_result {"job_id":"<returned UUID>"}
artifact_read {"job_id":"<returned UUID>","name":"stdout.txt"}
```

The LJ example uses reduced units, FCC initial positions, NVE and `lj/cut`. Bounds: 2–8 cells per dimension (32–2048 atoms), 0–200000 steps, temperature 0.01–10, density 0.1–1.5, timestep 0.0001–0.01, and seed 1–900000000. These are workload limits, not proof that every combination is physically meaningful.

## Persistence and limits

Each job stores `input.in`, `job.json`, `state.json`, `stdout.txt`, `stderr.txt`, engine metadata and final `result.json` in `jobs/<UUID>/`. Input SHA-256 values are rechecked by the worker. Metadata writes are atomic. An independent worker owns the timeout, cancellation and finalization; a restarted MCP server retrieves its records.

Final states are `succeeded`, `failed`, `timed_out`, `cancelled`, and `output_limit`. A heartbeat older than 15 seconds produces `stale`: completion is unknown. No success is guessed and no unrelated PID is killed. Stale jobs count against the parallel limit until an operator inspects them. Keep the environment installed while jobs are active. OS shutdown, logoff/session cleanup, worker crashes and deleted environments are outside this persistence guarantee.

| Limit | Value |
|---|---|
| Parallel jobs | 2 by default; `LAMMPS_MAX_PARALLEL=1..32` |
| Worker wall timeout | Explicit per job, 1–86400 seconds |
| Script | Nonempty UTF-8 without NUL, ≤1 MiB |
| Attachments | ≤20 flat text files; script + files ≤4 MiB |
| Captured stdout + stderr | ≤16 MiB total; worker terminates on overflow |
| Tool log tails | 8 KiB per stream |
| Artifact page | ≤64 KiB |

The captured-output cap is **not a filesystem quota**: trusted scripts may create other files of arbitrary size. Logs and bundles may contain research data; retention and cleanup belong to the operator. No deletion tool is exposed.

## Trusted scripts

For local stdio use, set `LAMMPS_ALLOW_TRUSTED_INPUT=1` only to run trusted scripts. HTTP mode deliberately refuses this setting. Example interface:

```json
{
  "input_script": "units real\natom_style full\nread_data polymer.data\n...",
  "files": {"polymer.data": "<actual LAMMPS data text>"},
  "timeout_seconds": 3600
}
```

The ellipsis is illustrative, not a runnable Tg model. **This mode is not an OS sandbox.** Scripts inherit the worker account's file and execution privileges. Adapter path validation does not constrain paths or commands inside a trusted LAMMPS script. Use an isolated OS user/container and resource quotas for untrusted code. Trusted script execution belongs to an operator-controlled deployment.

## Verify

```sh
python -m pip install '.[test,engine]'
python -m pytest tests -q
python -m ruff check src tests
```

Tests exercise validation, cancellation, timeout, output cap, persistence, stdio/HTTP MCP handshakes and real 256-atom LJ runs. HTTP tests additionally check exact proxy Host/Origin allowlists and rejection of trusted-script network mode. Real-engine tests skip explicitly when LAMMPS cannot initialize; skipped tests are not engine validation. Windows symlink tests skip if the account lacks permission. See the repository verification report (or `VALIDATION.md` in the standalone archive) for actual results. The full repository and standalone release archive include `scripts/accept_lammps.py`, which starts a separate supervisor and checks a real running job across client reconnection.

[中文说明](README.zh-CN.md). Adapter code is MIT-licensed; LAMMPS remains separately installed and GPLv2-licensed.
