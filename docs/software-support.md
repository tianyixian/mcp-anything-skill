# Software entry points and evidence

MCP Anything 0.4.4 accepts a software name, installation path, website, database, documented API or source repository and the operation the user wants. It is an agent development workflow. It does not automatically implement every application's features.

## Routes

| Route | Current implementation | Evidence and limits |
| --- | --- | --- |
| Software discovery | `discover_target.py`: PATH lookup, bounded Windows App Paths lookup, bounded directory inventory, URL classification | Never launches the target or fetches a URL. Script launchers, binaries, manifests and runtime markers remain unverified candidates. Missing names require a location; multiple matches require selection. |
| Windows runtime readiness | `references/windows-readiness.md`: installation, entry-point, dependency, UAC/session and minimal-input gate | A found `.exe`, partial installation, launcher-only start, `0xC0000135`, unexpected elevation or no-input solver exit remains candidate/blocked evidence until the intended runtime and operation are verified. |
| Installed command-line software | FFmpeg audio inspection and PCM16 WAV-to-FLAC example | Real FFmpeg 9.0.2 MCP calls and lossless decoded sample comparison on Windows. Limited local audio files, not arbitrary FFmpeg options. |
| Desktop automation API | Excel example through COM in an owned application instance | Requires Windows, desktop Excel and PowerShell 7. Supports bounded create/read/write-copy operations; see the example's actual validation record. PDF export did not complete acceptance on the test host and is not exposed. Does not control an existing personal workbook session. |
| Browser workflow | Notes UI adapter using Playwright and a dedicated headless browser | A real browser exercises the local demonstration app. This is not verification against arbitrary external sites, personal login sessions, captchas or changing third-party layouts. |
| Database | SQLite bounded read-only inspection | Existing actual SQLite MCP acceptance. No generic SQL executor. |
| Native scientific software | LAMMPS adapter with durable jobs | Historical real engine, HTTP and reconnection evidence. Adapter runtime unchanged in this release. |
| Science workflow recipes | Public PVDF, functional PI and self-healing binder contracts | Workflow import and missing-input preflight were checked; candidate MCP services and scientific conclusions still require a real target environment and inputs. See [workflow catalog](workflow-catalog.md). |
| Optional REA analysis | Available REA MCP tools or documented CLI, selected as needed | REA 6.8.0 was called through MCP to inspect an actual installed FFmpeg directory. No native reverse-engineering provider was needed for that call. |
| Arbitrary desktop UI / native reverse engineering | Skill decision and verification guidance | No universal desktop automation engine is bundled. Each additional software workflow needs an actual adapter, prerequisites and a separate acceptance check. |

## A capability's status

- **Discovered:** a candidate interface has been identified; the operation has not been verified.
- **Implemented:** execution code exists; real acceptance is still required.
- **Verified:** an actual MCP call produced the checked software state or artifact on the recorded version/environment.
- **Blocked:** the missing prerequisite or unresolved interface is named. Other verified operations can still be delivered.

The included scaffold remains scaffold-only until implemented. Merely listing a tool, recognizing an executable, accepting a click or generating a request is insufficient to mark an operation verified.

## How REA fits

REA supplies optional observations about packaged applications, native code or runtime behavior. MCP Anything remains independent and uses the evidence to choose an execution route. A delivered adapter needs REA only if its actual runtime calls REA. The FFmpeg, Excel and browser examples do not require it.

REA's recorded AgentEnv export answers from retained observations/local derived state. It can be a fixture or training environment, but it is not a live connection to the original software. This distinction is retained in the [skill's REA guide](../skills/mcp-anything/references/rea.md).

See [skill validation](skill-validation.md), [REA acceptance](rea-validation.json), and each example's README/validation record for the checks actually performed.
