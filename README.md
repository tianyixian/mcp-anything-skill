# MCP Anything Skill

**Give your agent a software name, installation path or website, and the task you need. Get useful MCP tools and evidence that they work.**

[简体中文](README.zh-CN.md) · [Install](docs/skill-install.md) · [Examples](examples) · [Validation](docs/skill-validation.md)

MCP Anything is an agent skill for turning existing software into tested MCP integrations. Source code is optional. The agent locates the target, chooses a supported API, command, scripting/desktop interface or browser workflow, implements useful operations, and checks their real results. GitHub repositories remain one supported starting point.

The skill runs inside your existing coding agent. It needs no separate model API key or hosted generation service. [REA](https://github.com/morluto/rea) is an optional investigation tool for packaged or poorly documented software, not a mandatory dependency. Target applications still need their own dependencies and access. **“Anything” describes the entry points; every delivered operation must be implemented and tested for its target.** See the [support and evidence matrix](docs/software-support.md).

## Install and ask

Clone this repository, then copy `skills/mcp-anything` into your agent's skills directory. For Codex on macOS/Linux:

```sh
git clone https://github.com/tianyixian/mcp-anything-skill.git
mkdir -p ~/.codex/skills
cp -R mcp-anything-skill/skills/mcp-anything ~/.codex/skills/
```

For Claude Code, use `~/.claude/skills/`. Windows commands and ZIP installation are in [the installation guide](docs/skill-install.md). Open a new agent session after installation. The folder format is portable; host discovery and configuration should be checked in the client you use.

Then ask:

> Use $mcp-anything with the FFmpeg installed on this machine. I need to inspect audio and convert WAV to FLAC. Find the executable, implement the tools and verify the converted samples.

Or:

> Use $mcp-anything with Microsoft Excel. Create a test workbook, read selected cells and update them in a new copy. Use the installed application's automation interface and verify the saved files.

> Use $mcp-anything with this notes website. Expose listing and creating notes, use a dedicated browser session, and read back the new note after refreshing.

Repository URLs, local databases and documented APIs work as inputs too. Specify the capability you need; supplying a software name does not imply every feature will be exposed.

## What you get

- A capability-specific adapter with typed inputs and structured results.
- Installation instructions and client configuration for the chosen transport.
- A short usage guide with exact inputs, a tested recipe, and failure recovery.
- A version/source record, actual execution evidence, and clear limitations.

The agent first looks for an existing maintained MCP integration. It prefers supported APIs, CLI commands, libraries and plugin/desktop automation interfaces; browser or desktop UI automation is available when the task needs it. Optional REA investigation can help locate a usable interface. Long computations retain submission/status/result/cancellation behavior. Writes need a readback or artifact check, including UI operations.

The helpers provide bounded software discovery and repository inventory, an honest stdio scaffold (`adapter_ready: false`), and a protocol checker. Discovery never launches the target or fetches a URL; it reports unverified candidates. The helpers do not automatically translate arbitrary software or API schemas. The agent still implements the integration.

```sh
python skills/mcp-anything/scripts/discover_target.py ffmpeg --task "inspect and convert audio"
python skills/mcp-anything/scripts/discover_target.py "Microsoft Excel" --task "read cells and save an updated copy"
python skills/mcp-anything/scripts/discover_target.py https://example.com/app --kind url
```

Name lookup covers `PATH` and bounded Windows App Paths registrations. Unresolved or ambiguous names require an installation path or a selection. Discovery reports may contain local paths and should be reviewed before sharing.

## Try the examples

| Example | Useful operations | Dependencies | Evidence |
| --- | --- | --- | --- |
| [FFmpeg](examples/ffmpeg) | Inspect audio; convert PCM16 WAV to a new FLAC | Installed FFmpeg/ffprobe, Python and MCP SDK | Actual stdio calls, decoded sample comparison, no-overwrite checks |
| [Excel](examples/excel) | Create/read a workbook and update a new copy | Windows, installed desktop Excel, PowerShell 7, Python and MCP SDK | Owned Excel COM instance and temporary workbooks; see example validation |
| [Browser](examples/browser) | List and create notes through a web UI | Node, Playwright Core, browser, Python and MCP SDK | Real browser against a local demo app; see example validation |
| [SQLite](examples/sqlite) | Discover tables, inspect columns, preview bounded rows | Python 3.11+, MCP SDK; SQLite ships with Python | Real temporary database, actual MCP calls, read-only and input checks |
| [LAMMPS](adapters/lammps/README.md) | Run a small LJ simulation; submit, poll, cancel and read artifacts | Separately installed LAMMPS; MPI/runtime requirements vary | Real Windows/Linux engine tests, stdio, platform HTTP and client reconnection |

The converter skill is **0.4.1**; the LAMMPS adapter remains **0.2.0**. These examples cover specific operations, not all applications or arbitrary GUI workflows. REA's recorded AgentEnv bundles answer from captured evidence; they are not proof of live application access. A small LJ simulation validates the LAMMPS integration, not polymer Tg predictions. Its shared HTTP service does not provide per-user job isolation.

Completion follows the user's requested operations: reading a model cannot complete a requested solve. The [operation gate](skills/mcp-anything/references/operation-acceptance.md) checks pinned call reports and outcome artifacts; the [wheel checker](skills/mcp-anything/references/verification.md) detects stale Python code in a release. The stdio checker has been exercised with SDK 1.30.0 and 2.3.0 in separate environments.

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

Inspired in part by [gabrielekarra/mcp-anything](https://github.com/gabrielekarra/mcp-anything), which also includes a skill/plugin. [REA](https://github.com/morluto/rea) informs the optional investigation route. This project is independently implemented; it calls available REA tools when needed, rather than maintaining a REA fork. No upstream source or templates were copied. See [related work](docs/related-work.md), [software dependencies](docs/software-dependencies.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

Original skill, adapter code and documentation: [MIT](LICENSE). Upstream software retains its own license; LAMMPS is GPLv2 and is installed separately.
