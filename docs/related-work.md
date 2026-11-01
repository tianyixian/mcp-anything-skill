# Related work

We reviewed [gabrielekarra/mcp-anything](https://github.com/gabrielekarra/mcp-anything) at commit [`a7a45a537709ca6c9e79c3739508fef7b3ba90af`](https://github.com/gabrielekarra/mcp-anything/tree/a7a45a537709ca6c9e79c3739508fef7b3ba90af) on 2026-11-01. This was a source review; we did not run its generator or benchmark its results. Its source is Apache-2.0 licensed. No source or templates were copied into this project.

It currently includes a [Claude Code plugin/skill](https://github.com/gabrielekarra/mcp-anything/blob/a7a45a537709ca6c9e79c3739508fef7b3ba90af/plugins/mcp-anything/skills/generate/SKILL.md), in addition to its CLI generator. Describing it as “not a skill” would be inaccurate for this revision.

| Aspect | Referenced project at the reviewed revision | This project |
| --- | --- | --- |
| Main mechanism | Generator CLI with scan and brief-driven build paths; plugin wraps that CLI | Portable skill guiding the user's coding agent, supported by small helpers |
| Interfaces | Source/spec detectors and Python/TypeScript emitters | Agent selects and implements a documented library, CLI, HTTP or database interface; Python stdio scaffold supplied |
| Tool selection | Use-case brief, scope selection, grouping and descriptions | Start from the user's tasks; keep permissions and input shapes explicit |
| Handoff | Generates server packages and agent usage guides | Deliver installed adapter, exact usage recipe, client config and execution evidence |
| Validation focus | Conformance tools and protocol tests are present; we did not run them | Require a real useful call and an observable result; distinguish fixtures, missing dependencies and remote access |

The useful ideas we adopted are a short task brief, deliberate capability selection, compact outputs, and a usage guide for the agent that will call the generated server. We do not mandate CRUD grouping: a read tool and a destructive write tool can need different permissions and parameters.

MCP Anything Skill does not claim a new MCP protocol, exhaustive automatic conversion, or a benchmark advantage over that project. Its practical focus is implementation that can be inspected and exercised, including the lifecycle of long computations. The SQLite and LAMMPS examples document the actual scope we have tested.
