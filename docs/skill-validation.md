# MCP Anything Skill 0.3.0 — validation

Validation performed on 2026-11-01. Local environment: Windows, Python 3.13.5, official MCP Python SDK 1.30.0. SQLite acceptance used SQLite 3.50.2. The converter skill is version 0.3.0; the LAMMPS adapter remains version 0.2.0.

The final combined local suite completed with **75 passed, 7 skipped in 51.01 seconds**. All seven skips require Windows symlink-creation privileges unavailable to this account; actual Windows junction tests passed. Real LAMMPS stdio and HTTP tests passed in this environment. Ruff correctness checks and the skill metadata validator also passed.

## What was exercised

- The skill-creator metadata validator passed for `mcp-anything`.
- The inventory and scaffold tests checked that repository source is not executed, existing work is preserved, and linked directories cannot escape the selected tree. Actual Windows junction tests passed; symlink tests require privileges unavailable in this account.
- The generic stdio checker ran real MCP sessions against small fixture servers. Its 15 focused tests checked declared successful calls, expected errors, mismatch detection, missing tools, environment inheritance, process failure, timeout and output preservation. A shutdown-timeout regression ensures that a previously successful discovery cannot produce a success exit code after cleanup fails. These fixtures test the checker, not an external software integration.
- An independent agent used the revised skill to implement the SQLite example from a request for table discovery, column inspection and bounded read-only row previews. Real MCP calls returned the known sample rows, invalid requests were rejected, and the database file hash remained unchanged. Its checked-in acceptance record includes Python, SQLite and SDK versions. This was a scoped engineering reuse check, not a comparative benchmark.
- SQLite's 9 tests include JSON-escaped table/column names and an empty table whose metadata alone exceeds the output bound. All three tools enforce the final serialized-result limit.
- Release tests verified that a skill-only archive builds without adapter sources or a LAMMPS wheel, excludes deployment notes and runtime directories, preserves component versions, verifies hashes, and refuses links/junctions.

## Reproduce

From the full source repository, using Python 3.11+:

```sh
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e adapters/lammps
python -m pytest skills/mcp-anything/tests adapters/lammps/tests examples scripts/tests -q
python examples/sqlite/verify.py
python scripts/build_release.py --target skill --output dist
```

For the standalone skill ZIP, its helper tests are in `mcp-anything/tests/`. Install `pytest`, `pytest-asyncio` and the MCP SDK in an isolated environment, then run `python -m pytest mcp-anything/tests --asyncio-mode=auto`. The ZIP does not contain the SQLite example, LAMMPS runtime or full repository development lock. The full source repository contains those examples and the locked test dependencies.

## Evidence boundaries

Historical LAMMPS real-engine tests cover Windows/Linux, stdio, platform HTTP and a running job surviving client reconnection. They are recorded separately in the full source repository's `docs/validation.md`; they are not new scientific results from the 0.3.0 skill work. Cross-account platform access was not established.

No claim is made that every GitHub repository is convertible, that every client UI was exercised, or that automatic OpenAPI/GraphQL/gRPC generation exists. The SQLite example is intended for trusted local database snapshots; adversarial files, concurrent writers and remote deployment are outside its acceptance scope. The external similarly named project's source was reviewed, but its generator was not executed or benchmarked.

GitHub Actions is configured for Windows/Linux and Python 3.11/3.13. Consult the repository's actual run for CI status; the workflow file alone is not a passing run. Real LAMMPS integration tests explicitly skip when the separately installed engine is unavailable.
