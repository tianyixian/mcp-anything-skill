# Optional REA investigation

MCP Anything remains an independent integration skill. [REA](https://github.com/morluto/rea) can supply evidence when the chosen task depends on a packaged application, native binary or unclear runtime behavior. Reuse ordinary documentation/source tools for an already understood API or CLI. REA is optional and is not bundled with this skill.

## Use an available connection

Prefer the REA MCP tools actually advertised by the connected server; inspect their current schemas. A locally installed CLI is an alternative. Record the REA version and relevant provider version. Repository `main`, a downloaded skill and an installed release may expose different capabilities.

Useful static entry points documented by REA include:

| Question | MCP tool | CLI equivalent |
| --- | --- | --- |
| What is in this unknown installation directory? | `inspect_desktop_application` | `rea inspect-desktop-application /absolute/app --json` |
| What modules and interfaces are in this JavaScript/Electron tree or ASAR? | `analyze_javascript_application` | `rea analyze-javascript-application /absolute/app --json` |

Confirm options against the installed release. The directory inspector reports runtime candidates and follow-up probes; it does not launch the application. JavaScript/Electron static analysis also does not establish that the discovered routes or IPC endpoints are callable in the actual session. Native decompilation requires a compatible separately installed provider such as Ghidra, Hopper or IDA; do not make that dependency mandatory for ordinary software conversion.

If REA is absent, state that this optional route is unavailable and continue with other evidence when sufficient. Install or register it only when needed for the requested task and within the user's authorized scope; missing REA is not itself a reason to change global agent configuration. Check actual prerequisite requirements before acquiring a release.

## Convert evidence into a working adapter

Use REA to answer a narrow question: identify a runtime, locate a script/plugin surface, explain an argument or inspect a specific interaction. Retain the relevant evidence identifiers, limitations and target version. Do not copy an entire binary, recording or private response payload into a generic usage guide.

REA's passive CDP observations inspect existing browser state. Its separate `capture_browser_scenario` workflow can perform declared browser actions and record results. Neither observation alone nor one successful recorded sequence supplies a durable business adapter: implement parameters, login/session handling, state checks, error behavior and repeat-call semantics using the chosen execution mechanism.

REA's `environment-build` / exported AgentEnv bundles answer from retained observations and derived local state. They do not fetch results from the original application. Such a bundle can be useful as a fixture or training environment; label it accordingly. Verify a live adapter by actually calling the target software through MCP and checking its output or state.

REA used only for investigation belongs in the development record. An adapter that depends on REA at runtime must declare the needed version/provider, check availability and exercise that execution path. Prefer a direct stable interface when the investigation has established one.

References checked against REA commit `8c857ce56c68ca46d202db0c9571277974c9e167`:

- [Desktop inspection](https://github.com/morluto/rea/blob/8c857ce56c68ca46d202db0c9571277974c9e167/docs/desktop-applications.md)
- [Browser observation and scenario boundaries](https://github.com/morluto/rea/blob/8c857ce56c68ca46d202db0c9571277974c9e167/docs/browser-observation.md)
- [Recorded agent environments](https://github.com/morluto/rea/blob/8c857ce56c68ca46d202db0c9571277974c9e167/docs/agent-environments.md)
