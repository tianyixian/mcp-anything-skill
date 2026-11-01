# LAMMPS conversion record

This adapter is the first worked application of the `mcp-anything` skill in this repository. The skill is a reusable engineering procedure with executable helpers; it does not generate a complete scientific adapter from a URL alone.

## Source examined

- Repository: https://github.com/lammps/lammps
- Selected release: `stable_22Jul2025_update4`
- Commit: `611ca3b7f8525ba802373b04f9e3d632d515f7e3`
- License: GPL v2, as stated in the upstream README and LICENSE.
- Inspected interfaces: `python/lammps/core.py`, command-line `-in`, Python `lammps.file`, example `examples/melt/in.melt`, and upstream run/install documentation.
- Test engine distribution: `lammps==2025.7.22.4.0`, reports engine version `20250722`.

The local checkout is sparse, so the machine-generated inspection is an inventory of the checked-out interface files, not an audit of every file in LAMMPS.

## Interface decision

An MCP call must return promptly even when a simulation lasts hours. A per-job supervisor launches the scientific engine in a separate process, owns its timeout/cancel handling, and writes results to disk. A later MCP invocation can query the same job. This also fits harnesses that close MCP connections between agent calls.

The service provides a fixed-input Lennard-Jones demonstration and an explicitly enabled trusted-input path. The demonstration proves real execution without needing external material data. Trusted mode can accept a real material model, but supplies no automatic force-field selection or validation of Tg methodology.

The MCP transport is stdio, using the official Python SDK. The LAMMPS library runs in a separate child process so native engine stdout cannot corrupt MCP messages. Operators may instead select an existing LAMMPS executable. MPI cluster scheduling and remote authentication are outside this version.

## Acceptance

Check the actual outcomes in [validation.md](validation.md): source inspection, generated project, installation, MCP handshake, real-engine computation, restart behavior and negative cases. The input, output and engine version must accompany any claim of a successful computation. No synthetic fixture is accepted as scientific-engine validation.
