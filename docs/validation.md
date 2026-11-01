# Release validation — 0.2.0

The original 0.1.0 validation was executed on **2026-10-31 (Asia/Shanghai)**. The 0.2.0 HTTP extension is recorded separately below. Local platform: Windows 11 x86_64, Python 3.13.5, MCP Python SDK 1.30.0. LAMMPS distribution: 2025.7.22.4.0, engine 22 Jul 2025 Update 4. Microsoft MPI 10.1.1 was provided in the isolated test runtime; no engine/MPI files are redistributed.

## Original 0.1.0 evidence

| Check | Actual result |
| --- | --- |
| Skill metadata | skill-creator validator passed |
| Static upstream inspection | 1,423 checked-out files inventoried; fixed commit and sparse-checkout status recorded; source code not executed |
| Skill and adapter suite | **38 passed, 2 skipped**; real LAMMPS test passed |
| Skips | Windows account cannot create symbolic links: two symlink tests skipped; separate Windows junction rejection test passed |
| Protocol | Real stdio initialization, discovery of 7 tools, typed input bounds and structured output schemas |
| Real Python-library backend | 256 atoms, 100 steps, successful exit; 11 thermodynamic rows, engine version and input hash preserved |
| Installed wheel with native executable backend | Separate environment loaded the built wheel and performed real MCP calls; 256 atoms and 100 steps succeeded |
| Disconnect while running | Native backend: observed `running` plus engine PID, closed submitting MCP connection, reconnected; 2,048 atoms completed 5,000 steps successfully |
| Second skill application | Local `tiny-stats` Python library inspected, scaffold generated and customized, installed separately, MCP mean([1,2,3,10]) returned 4.0; empty input returned MCP error |
| Failure/lifecycle fixtures | Invalid arguments, trusted input gate, engine failure, timeout, cancellation, parallel limit, output cap, stale state, artifact pagination and contended interprocess lock exercised |
| Build | Installable wheel and source distribution built using hatchling 1.33.0; wheel includes the MIT license |
| Source checks | Ruff correctness checks passed; distribution excludes private runtime data and deployment identifiers |

The second skill application was performed by the main implementer after an independent agent hit service rate limits. It is a practical reuse check, not a blind external evaluation. A separate reviewer examined the source and identified packaging and lifecycle issues that were corrected.

## 0.2.0 HTTP extension

Version 0.2.0 adds stateless Streamable HTTP with JSON responses, a configurable `/mcp` endpoint, `GET /health` and `GET /` service information. Existing stdio behavior and durable job records remain available. Shared HTTP startup refuses trusted-script execution. Proxy Host and Origin configuration retains DNS rebinding protection and requires exact allowlist entries; these checks are not user authentication.

The full 0.2.0 suite was executed on **2026-11-01 (Asia/Shanghai)** on the Windows environment above: **43 passed, 2 skipped in 33.68 seconds**. The two skips remain the symlink-permission tests; the real stdio and HTTP LAMMPS tests passed.

The five HTTP tests cover an actual listening service, MCP initialization/discovery/calls, a real 256-atom/100-step LAMMPS job, rejection of an unlisted Host/Origin, configured proxy Host/Origin acceptance, trusted-input startup rejection, and invalid allowlist values. The historical 38-pass figure above belongs to the 0.1.0 suite; 43 passes is the observed combined 0.2.0 result.

The 0.2.0 wheel and source distribution have been built. On **2026-11-01**, the complete suite ran on a Qizhi Linux CPU instance with Python 3.12.3, the hashed dependency lock, LAMMPS 2025.7.22.4.0 and MPICH 4.3.2: **44 passed, 1 skipped in 12.97 seconds**. The skip is the Windows-only junction test. Both real-engine stdio and HTTP tests passed.

A separate Qizhi notebook also completed HTTP acceptance against a different CPU instance running native LAMMPS 7 Feb 2024 Update 1: seven-tool discovery, rejected invalid/trusted input, a real 256-atom/100-step run, artifact reading, and a running 2,048-atom/5,000-step job surviving client disconnect and a new MCP session. Sanitized evidence is in [acceptance-qz-http.json](acceptance-qz-http.json). This demonstrates engine execution, not a material-property validation.

**The platform HTTPS gateway passed real CPU acceptance on 2026-11-01.** The Serving instance reached `RUNNING`, and gateway health returned HTTP 200. A client in an independent Qizhi notebook then completed MCP acceptance through the routed HTTPS `/mcp` endpoint: seven tools with structured output schemas, engine probe, invalid-input and trusted-input rejection, a successful 256-atom/100-step run, and artifact reading. The deployed Python-library engine reported version **20250722**, distribution **2025.7.22.4.0**.

The same gateway test observed a running 2,048-atom job, disconnected the HTTP client, opened a new HTTP client and MCP session, and retrieved successful completion at 5,000 steps. This verifies client reconnection; the HTTP server was not restarted. Sanitized evidence is retained in [acceptance-qz-gateway.json](acceptance-qz-gateway.json). Exact endpoint, live job UUIDs and engine process ID are removed from the public copy. **Cross-account access was not tested**; this result does not establish access for every platform user or per-user job isolation. Deployment identifiers and operational configuration remain outside this portable release.

## Retained evidence

- [Source inspection](lammps-source-inspection.json): GitHub URL, commit `611ca3b7f8525ba802373b04f9e3d632d515f7e3`, candidate interface and license files.
- [LAMMPS conversion decisions](lammps-conversion.md).
- [Native backend and active-reconnect acceptance](acceptance-native.json).
- [Second skill application](skill-forward-test.json).
- [Qizhi cross-instance HTTP engine acceptance](acceptance-qz-http.json).
- [Qizhi platform HTTPS gateway and client-reconnect acceptance](acceptance-qz-gateway.json).
- [Python-library input, log and result](../adapters/lammps/examples/verified-lj/).

Both backends used the same input SHA-256 `db1901ccb6dd513c735b329f9f154535f455dc3c1a1377409e0697c988185dda`. At step 100 the recorded temperature was 0.51995916 and total energy -5.2854317 in reduced LJ units. These values demonstrate a reproducible engine call; they are not a fitted material property, a physical convergence claim, or a glass-transition temperature.

## Reproduce

From the full repository root:

```sh
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install -e ./adapters/lammps
python -m pip install -r requirements-engine.txt
python -m pytest skills/mcp-anything/tests adapters/lammps/tests -q
python -m ruff check --select E9,F63,F7,F82 skills adapters scripts
python -m build ./adapters/lammps
python scripts/accept_lammps.py --workspace /absolute/test-workspace --output acceptance.json
python scripts/build_release.py --output dist
```

Supply `--python /absolute/other-env/python` and `--executable /absolute/lmp` to acceptance when testing a separately installed wheel with an existing native engine. On Windows use absolute drive paths. The acceptance runner starts a supervisor outside the MCP server process tree, requires a real engine and fails instead of skipping when one is unavailable. Ordinary pytest marks an unavailable engine as an explicit skip.

In a standalone adapter archive, install with `python -m pip install '.[test,engine]'` and run `python -m pytest tests -q`. Or install the included `packages/lammps_mcp-0.2.0-py3-none-any.whl` and supply your own LAMMPS installation. Dependencies and engine platform requirements still apply; these are not offline all-dependency bundles.

For the local HTTP checks alone, run `python -m pytest adapters/lammps/tests/test_http.py -q` from the repository root. These tests start a local HTTP server and an independent supervisor. The real-engine HTTP test explicitly skips if LAMMPS cannot initialize; inspect skips before claiming engine validation. HTTP configuration and platform routing requirements are documented in the [architecture](architecture.md#streamable-http-in-020) and [adapter README](../adapters/lammps/README.md#shared-platform-http-service).

## Explicit limits

- Windows was executed locally and Linux Python 3.12 was executed on Qizhi. Linux/Windows Python 3.11/3.13 CI is configured, but no remote GitHub CI run or macOS acceptance is claimed.
- Windows requires a separately started supervisor. Merely detaching a subprocess was insufficient because the MCP client cleaned up its entire server process tree. The release checks this prerequisite and the real reconnect path.
- A second installation run exposed a Windows mandatory-lock race: reading the lock byte before acquiring it could fail under contention. Initialization now checks file size without reading the locked byte, and a dedicated two-process regression verifies waiting and successful acquisition.
- OS reboot, user logoff/process cleanup, corrupt/deleted workspace and worker crashes are outside the persistence guarantee. Stale work remains visibly unknown and requires operator inspection.
- CPU engine calls across Qizhi instances and through the platform HTTPS gateway were tested from an independent notebook. Cross-account access was not tested, and universal user access is not claimed. The gateway test covered client disconnect/reconnect, not an HTTP server restart. No remote GPU/distributed MPI cluster or newly deployed agent harness was tested.
- Custom scripts are trusted execution through operator-controlled stdio, not an OS sandbox; HTTP mode disables them. Captured stdout/stderr have a byte limit; files written directly by trusted scripts do not.
- HTTP has no built-in user authentication or per-user job ownership. Exact Host/Origin checks are routing protections; platform access control and a non-private shared demonstration workspace are required.
- No new polymer Tg measurements or simulations were produced. Scientific data generation requires a separately reviewed material model and simulation protocol.
