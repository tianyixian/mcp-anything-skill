# Changelog

## 0.3.0 — MCP Anything Skill

- Rename the converter to `mcp-anything` and the public repository to `mcp-anything-skill`.
- Explain installation and usage in English and Chinese, including migration from `github-to-mcp`.
- Add interface guidance for libraries, CLI programs, documented APIs and databases; prefer an existing maintained MCP when suitable.
- Require a concise agent-facing usage guide with exact inputs and a tested recipe.
- Add a reusable MCP stdio checker and a runnable SQLite example.
- Package the skill independently of LAMMPS, with dedicated installation and validation documents.
- Credit the independently developed `gabrielekarra/mcp-anything` project accurately, including its current plugin/skill.

The LAMMPS adapter remains at 0.2.0. This release does not change its scientific model, public HTTP service or job-management behavior.

## 0.2.0 — LAMMPS HTTP delivery

Added Streamable HTTP to the LAMMPS adapter and validated actual engine execution and client reconnection through a platform gateway. Historical validation is retained in `docs/validation.md`.
