# MCP Anything Skill 0.4.0 — validation

Validation performed on 2026-11-03. Local host: Windows, Python 3.13.5, official MCP Python SDK 1.30.0. The converter skill is 0.4.0; the LAMMPS adapter remains 0.2.0. The [0.3.0 validation record](skill-validation-0.3.0.md) is preserved separately.

The final combined local suite completed with **123 passed, 9 skipped in 94.46 seconds**. All nine skips require Windows symlink-creation privileges unavailable to this account; actual Windows junction tests passed. FFmpeg, Excel COM, the browser example, SQLite and the installed LAMMPS engine were exercised. Ruff correctness checks and the skill metadata validator passed.

## New interfaces actually exercised

| Interface | Real software result | Evidence |
| --- | --- | --- |
| Software discovery | Found installed FFmpeg via PATH and Excel via Windows App Paths without launching them; directory and URL inputs stayed unverified | Helper tests and independent forward review; Windows batch-launcher omission found and fixed |
| CLI | FFmpeg 9.0.2 converted a one-second WAV to FLAC through MCP; 16,000 decoded PCM samples matched exactly | `examples/ffmpeg/validation.json` |
| Desktop automation | Excel 16.0 created, read and saved a changed copy of a disposable workbook through MCP; source hash remained unchanged and owned processes closed | `examples/excel/validation.json` |
| Browser | Playwright Core 1.62.1 and Edge 156.0.4314.58 created/read notes through MCP and the actual UI; refresh and a new browser read the saved state | `examples/browser/validation.json` |
| Optional REA | REA 6.8.0 with Node 24.22.1 was connected through MCP; static inspection checked PE header observations for three installed FFmpeg binaries | `docs/rea-validation.json` |

The Excel example needs PowerShell 7. PDF export did not complete acceptance on this host and is not exposed. The browser target is an original local demonstration app, not an independently maintained third-party website. REA inspection does not run the target program or establish a callable interface by itself.

An independent browser review found that a cancelled call could leave a late response in the worker stream and that a timeout prevented subsequent recovery. Both were fixed: the affected worker is discarded, the next explicit call can create a new session, and writes are never automatically replayed. Five subprocess regressions cover cancellation, timeout, incorrect response identity, invalid JSON and EOF; an independent follow-up confirmed all five pass. Real browser canary tests also check that direct cross-origin requests and redirects do not reach a second server.

## Installation and packaging

A new isolated Python environment was populated from `requirements-dev.lock` with hash verification. Real FFmpeg and SQLite acceptance passed in that environment. The browser dependency was separately installed with `npm ci --ignore-scripts` from its pinned lockfile, followed by real browser acceptance. These checks do not claim a clean Office installation; the licensed Excel and media/browser executables were already installed on the host.

Release tests check independent skill packaging, source/archive boundaries, link refusal, stable hashes and unchanged adapter versioning. The release builder excludes `node_modules`, environments, workspace data and private deployment notes. Archive extraction and installed-skill discovery are checked during packaging.

## Reproduce

From the full project using Python 3.11+:

```sh
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e adapters/lammps
npm ci --ignore-scripts --prefix examples/browser
python -m pytest skills/mcp-anything/tests adapters/lammps/tests examples scripts/tests -q -ra
python examples/ffmpeg/verify.py
python examples/excel/verify.py
python examples/browser/verify.py --node /absolute/node --browser /absolute/chrome
python scripts/build_release.py --target skill --output dist
```

Install each optional target runtime separately. For pytest to exercise the browser, set `BROWSER_MCP_NODE` and `BROWSER_MCP_EXECUTABLE` to actual executable paths. The Excel verifier requires Windows, PowerShell 7 and an activated desktop Excel installation. Missing target runtimes cause explicit test skips, not fabricated acceptance. Consult each example README for its supported input scope and prerequisites.

The standalone skill ZIP contains the discovery/inventory/scaffold/checker scripts, their tests and conditional references. It does not bundle the example apps, target runtimes or REA. Run its helper tests after installing `pytest`, `pytest-asyncio` and the MCP SDK in an isolated environment.

## Scope of the evidence

The new work proves specific installed-software and browser operations, and one real optional REA inspection. General desktop UI automation, all Office features, third-party website login recovery, arbitrary binary reverse engineering and universal conversion success are not established. No controlled comparison against other MCP generators was performed.

Historical LAMMPS deployment and real-engine evidence remains in `docs/validation.md`. No new scientific material-property results or cross-account platform access claims are made. Existing deployed runtime behavior is unchanged.

GitHub Actions targets Windows/Linux and Python 3.11/3.13. It installs the optional browser example dependency, enables browser integration when a supported executable is present, and installs FFmpeg on Linux. The actual run determines CI status; the workflow definition is not evidence of a completed run.
