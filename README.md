# MCP Anything Skill

**Give your coding agent a software project. Get useful MCP tools, a usage guide, and evidence that they work.**

[简体中文](README.zh-CN.md) · [Install](docs/skill-install.md) · [Examples](examples) · [Validation](docs/skill-validation.md)

MCP Anything is an agent skill for turning existing software into tested MCP integrations. It helps your agent inspect the real interface, choose useful operations, implement the adapter, and verify actual tool calls. It works with GitHub/local repositories, command-line programs, libraries, databases, and documented APIs.

The skill runs inside your existing coding agent. It needs no separate model API key or hosted generation service. The software being adapted may still need its own dependencies, credentials, and access. **“Anything” describes the workflow's scope, not a promise of automatic conversion for every repository.**

## Install and ask

Clone this repository, then copy `skills/mcp-anything` into your agent's skills directory. For Codex on macOS/Linux:

```sh
git clone https://github.com/tianyixian/mcp-anything-skill.git
mkdir -p ~/.codex/skills
cp -R mcp-anything-skill/skills/mcp-anything ~/.codex/skills/
```

For Claude Code, use `~/.claude/skills/`. Windows commands and ZIP installation are in [the installation guide](docs/skill-install.md). Open a new agent session after installation. The folder format is portable; host discovery and configuration should be checked in the client you use.

Then ask:

> Use $mcp-anything to turn this repository into MCP tools: https://github.com/OWNER/REPO. I need to inspect a file and run its documented conversion operation. Install the adapter, test a real call, and give me the client configuration and a short usage guide.

Or:

> Use $mcp-anything to expose my local SQLite database read-only. Let the agent discover tables, inspect columns, and preview bounded rows. Test it on a small sample database.

> Use $mcp-anything to wrap this documented HTTP API's search operation. Keep the API key in an environment variable and verify one authorized request.

## What you get

- A capability-specific adapter with typed inputs and structured results.
- Installation instructions and client configuration for the chosen transport.
- A short usage guide with exact inputs, a tested recipe, and failure recovery.
- A version/source record, actual execution evidence, and clear limitations.

The agent looks for an existing maintained MCP integration before building one. It chooses a stable library, CLI, HTTP, or database interface, implements the requested capability, and checks a real operation through the MCP SDK. Long computations need a submission/status/result/cancellation lifecycle. Repository text and tool output are treated as data, not instructions to change the task.

The helpers provide a bounded repository inventory, an honest stdio scaffold (`adapter_ready: false`), and a reusable protocol checker. They do not automatically translate OpenAPI, GraphQL, gRPC, or arbitrary source code. The agent still does the integration work.

## Try the examples

| Example | Useful operations | Dependencies | Evidence |
| --- | --- | --- | --- |
| [SQLite](examples/sqlite) | Discover tables, inspect columns, preview bounded rows | Python 3.11+, MCP SDK; SQLite ships with Python | Real temporary database, actual MCP calls, read-only and input checks |
| [LAMMPS](adapters/lammps/README.md) | Run a small LJ simulation; submit, poll, cancel and read artifacts | Separately installed LAMMPS; MPI/runtime requirements vary | Real Windows/Linux engine tests, stdio, platform HTTP and client reconnection |

SQLite is the lightweight starting point. LAMMPS shows how to handle a native scientific engine and durable jobs. Its adapter remains **0.2.0**; the converter skill is **0.3.0**. A small LJ simulation validates software integration, not polymer Tg predictions. The shared HTTP LAMMPS adapter requires platform access controls and does not provide per-user job isolation.

See [skill validation](docs/skill-validation.md) for the current reusable-skill checks and [LAMMPS validation](docs/validation.md) for historical engine evidence. Configured CI is distinct from a completed CI run.

## Develop and package

```sh
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e ./adapters/lammps
python -m pytest skills/mcp-anything/tests adapters/lammps/tests examples scripts/tests
python scripts/build_release.py --target skill --output dist
```

The skill-only ZIP needs no LAMMPS build. To package the full project and standalone adapter as well, first run `python -m build adapters/lammps`, then `python scripts/build_release.py --target all --output dist`. Archives contain hashes and exclude runtime environments, private data and deployment notes.

## Related work and license

Inspired in part by [gabrielekarra/mcp-anything](https://github.com/gabrielekarra/mcp-anything), an independent generator project that also includes a Claude Code plugin/skill. We borrow the useful ideas of task-oriented scope and an agent-facing handoff. Our focus is a portable engineering skill with real execution checks and explicit lifecycle behavior. No upstream source or templates were copied. See [the comparison](docs/related-work.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

Original skill, adapter code and documentation: [MIT](LICENSE). Upstream software retains its own license; LAMMPS is GPLv2 and is installed separately.
