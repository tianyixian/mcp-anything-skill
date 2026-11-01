# Upstream software

No upstream engine binaries or source trees are included in release archives.

| Component | Source | Version used for validation | Upstream license |
| --- | --- | --- | --- |
| LAMMPS | https://github.com/lammps/lammps | `stable_22Jul2025_update4`, commit `611ca3b7f8525ba802373b04f9e3d632d515f7e3`; Python distribution `2025.7.22.4.0` | GNU GPL v2; consult upstream notices for individual bundled components |
| MCP Python SDK | https://github.com/modelcontextprotocol/python-sdk | `1.30.0` | MIT |
| Microsoft MPI | https://github.com/microsoft/Microsoft-MPI | Windows test dependency only, 10.1.1 | Upstream Microsoft license; not included |

The LAMMPS adapter is independently written orchestration code. Users install the engine separately and retain its original license. The example uses a conventional FCC Lennard-Jones system and is not a fitted material model. The project does not include proprietary force-field data, licensed VASP assets or experimental datasets.

Public references used to establish the interface:

- https://docs.lammps.org/Run_basics.html
- https://docs.lammps.org/Python_install.html
- https://docs.lammps.org/Howto.html
- https://modelcontextprotocol.io/specification/2025-11-25

The protocol SDK negotiates a supported MCP version with each client. The LAMMPS adapter supports stdio and Streamable HTTP; it does not provide multi-user authentication or per-user job isolation.

## Related project

Design reference: https://github.com/gabrielekarra/mcp-anything at commit `a7a45a537709ca6c9e79c3739508fef7b3ba90af`, Apache-2.0. This independent project includes a CLI generator and a Claude Code plugin/skill. Its task-oriented scope selection and agent-facing handoff informed our workflow. No source files or templates were copied; this project's original code remains MIT licensed.

## SQLite example

The example uses Python's standard-library `sqlite3` driver (Python Software Foundation license) and the SQLite engine included in the user's Python installation (SQLite public domain). These runtimes are installed separately, not bundled. Sample records and the adapter are original project content. References: https://docs.python.org/3/library/sqlite3.html and https://www.sqlite.org/copyright.html.
