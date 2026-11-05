# MCP Anything Skill 0.4.2 — validation

Validation performed on 2026-11-05. Local Windows host, Python 3.13.5. The reusable skill is 0.4.2; the LAMMPS adapter remains 0.2.0. Previous [0.4.1](https://github.com/tianyixian/mcp-anything-skill/blob/v0.4.1/docs/skill-validation.md), [0.4.0](https://github.com/tianyixian/mcp-anything-skill/blob/v0.4.0/docs/skill-validation.md) and [0.3.0](https://github.com/tianyixian/mcp-anything-skill/blob/v0.3.0/docs/skill-validation.md) records retain their original scope.

## Windows runtime readiness

This release adds a reusable readiness gate prompted by the YJK 8.1 case. The gate requires an installation-completion check, separate identity for launcher/application/engine, dependency loading in the intended user context, recorded UAC/session requirements and a smallest valid input before an installed Windows program is called `runtime_ready`. A missing main entry point, loader error such as `0xC0000135`, unexpected administrator elevation or a solver exit caused by absent input remains `blocked` or diagnostic evidence. It cannot be turned into a pass by launching a temporary extraction, applying a patch or silently changing the user context. `runtime_ready` still requires a separate MCP operation acceptance check.

## Requested-operation completion

The local combined suite completed with **171 passed, 13 skipped in 97.41 seconds**. The skips are the Windows symlink privileges unavailable to this account plus two optional browser acceptance cases whose browser paths were not configured in this run; Windows junction checks ran. The suite includes the existing real FFmpeg, Excel, SQLite and LAMMPS checks. After the release version changed, packaging checks were repeated: 5 passed, 1 symlink skip. Ruff correctness checks and the skill metadata validator passed.

`assess_operations.py` keeps a requested operation incomplete while it is blocked, lacks real positive MCP calls, has failed assertions or references altered/missing artifacts. Protocol-only checks, negative-only calls, analysis and fixtures cannot verify an operation. Numerical tolerance checks reject nonfinite or overflowing comparisons. An independent forward test found two overflow/exception problems; both were fixed and independently rechecked.

A real SQLite stdio call was then recorded with the new checker. A retained input, call report and outcome artifact were hashed and assessed. The read-only request qualified as complete; adding an unimplemented requested write correctly made the overall request incomplete. The [sanitized summary](https://github.com/tianyixian/mcp-anything-skill/blob/v0.4.2/docs/operation-validation.json) describes those checks; it is not a canonical provider evidence bundle. The gate cannot establish provenance, choose relevant assertions or detect a request omitted from the ledger; these still need review.

The case evidence motivating the changes included a vendor model reader that worked while a requested solve was unavailable, and a vendor completion banner following a license failure. These changes do not claim a successful commercial-software solve. Case implementations and their current engine/license status are maintained separately.

## MCP client compatibility

The checker suite ran in separate environments with SDK **1.30.0** and **2.3.0**: **20 passed in each**. Actual stdio checks also passed with client 1.30.0 → server 2.3.0 and client 2.3.0 → server 1.30.0. The [cross-environment record](https://github.com/tianyixian/mcp-anything-skill/blob/v0.4.2/docs/checker-sdk-compatibility.json) retains SDK/protocol metadata and sanitized case results. These are protocol fixtures, not vendor-engine acceptance.

The checker adapts observed model fields and pagination APIs; it identifies missing/unsupported client APIs as `sdk_incompatible` before server launch. Reports retain the client SDK, negotiated protocol and positive/negative case kind. SDK 2 interactions requiring client input are outside this ordinary tool-result checker. Other SDK releases need their own verification; examples and the LAMMPS adapter still use MCP 1.x and are not migrated.

## Packaging

The new pure-Python wheel checker verified the existing LAMMPS 0.2.0 wheel's RECORD and byte equality for all **7 runtime Python files** against the tested source import root. Its regressions exercise stale/extra/missing/changed code, modified RECORD entries, unsafe paths, link refusal and size limits. Native and relocated code layouts remain unsupported. Package data and metadata receive RECORD checks only; source equality alone does not prove tests or dependencies work.

The standalone skill still packages without building LAMMPS. Source archives exclude environments, runtime data, vendor installers, private deployment notes and browser profiles. The unchanged LAMMPS archive must retain its published checksum when the full release is built. Installation and extracted-package checks are recorded separately from the source test suite.

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e adapters/lammps
npm ci --ignore-scripts --prefix examples/browser
python -m pytest skills/mcp-anything/tests adapters/lammps/tests examples scripts/tests -q -ra
python skills/mcp-anything/scripts/check_wheel.py adapters/lammps/dist/lammps_mcp-0.2.0-py3-none-any.whl --source-root adapters/lammps/src
python scripts/build_release.py --target skill --output dist
```

Use a separate environment with `mcp==2.3.0`, `pytest==9.2.0` and `pytest-asyncio==1.4.1` for the SDK 2 checker suite. The main locked environment must remain independent. Consult example READMEs for actual target runtimes; absent software causes explicit skips. Browser pytest acceptance needs `BROWSER_MCP_NODE` and `BROWSER_MCP_EXECUTABLE`. Excel needs Windows, PowerShell 7 and desktop Excel. CI configuration is not evidence that a particular run passed; inspect the actual run.
