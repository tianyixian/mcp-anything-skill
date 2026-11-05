# Verification and release

Use the actual MCP SDK client to initialize a stdio session, list tools, validate their schemas and test each requested operation against its completion condition. Start the installed entry point rather than only calling Python functions in-process. See [operation acceptance](operation-acceptance.md) for a request ledger and optional completion gate; successful supporting tools cannot close an untested requested operation.

For a trusted local stdio server, `python <skill>/scripts/check_mcp.py plan.json --output report.json` provides a reusable check. The command and arguments are an executable plus an array, never a shell expression. Relative paths use the caller's working directory. Set credentials in the process environment, not the plan. Only use operations authorized by the task; the checker really calls them.

```json
{
  "command": "python",
  "args": ["/absolute/path/server.py"],
  "required_tools": ["add"],
  "cases": [
    {"tool": "add", "arguments": {"a": 2, "b": 3}, "expect": {"sum": 5}},
    {"tool": "add", "arguments": {"a": "invalid", "b": 3}, "expect_error": true}
  ],
  "timeout_seconds": 30
}
```

Replace the illustrative tool with a real useful operation. `match: "exact"` requires exact structured equality; the default compares an object subset. Empty cases are labeled `protocol_only`. The checker reports case indices and pass/fail, not commands, inputs, result values or credentials. Keep a separate sanitized real-output artifact when provenance is needed. It requires the official MCP Python SDK and does not validate HTTP deployments. A passing checker only proves the declared assertions, not overall scientific or production correctness.

Run the checker in an environment compatible with the selected server's dependency constraints, recording the resolved SDK version. Keep official and custom servers in separate environments when their requirements conflict. The checker has been exercised with SDK 1.30.0 and 2.3.0, including cross-version client/server stdio calls. It records SDK/protocol metadata, adapts observed field/pagination APIs, and returns `sdk_incompatible` for an unsupported client instead of blaming the application. SDK 2 interactions requiring client input are outside this plain tool-result checker and return `unsupported_tool_response`. Other releases still require verification against their actual models/APIs.

For a computation adapter, preserve a real minimal input and an output that demonstrates execution. Check upstream license/runtime errors, required result files and a software-specific quantity (for example, LAMMPS atom count and final timestep) together. A completion banner can appear even after a license failure; zero exit alone is also insufficient. Record software version, units and tolerances where numbers are compared. Scientific validity beyond the example is a separate claim.

For an installed application, verify against the actual installed program rather than an API-shaped fixture. Use disposable test documents/data. Reopen or independently inspect saved/exported artifacts, verify the intended change and check preservation of unrelated input. For browser/UI workflows, exercise the named operation through MCP and inspect its final application state. Record the tested app build/site revision when available, OS, session mode and relevant locale. A selector match, successful click or screenshot is not by itself task acceptance.

Test repeat calls and cleanup for stateful automation. Establish what happens after login expiry, a missing control/dialog, a lost response or a second client when those conditions are relevant to the adapter. Read state before retrying a timed-out write, and report an uncertain outcome if it cannot be resolved. Check that closing the adapter leaves user-owned application sessions and documents intact. Do not advertise unattended, headless or concurrent use from a single interactive test.

When REA helped investigate the target, record the useful observations separately from adapter acceptance. A discovery report, decompilation, captured response or replayed AgentEnv result is analysis/fixture evidence. A live integration needs an actual call to the original application. If REA is a runtime dependency, test that path and its missing-provider error; otherwise verify the adapter with REA absent from its runtime configuration.

Test relevant negative cases: malformed schema, missing engine, path escape, disabled trusted operations, upstream error, timeout and cancellation. Long-job adapters also need restart/reconnect coverage while a job is running. Use controlled fixture executables for deterministic failures when needed, and label fixture evidence explicitly.

Package only selected source, configuration examples, docs and tests. Exclude virtual environments, engine binaries unless intentionally licensed/distributed, private inputs, logs containing deployment details, credentials and full chat transcripts. Include licenses, dependency constraints, hashes and instructions to repeat tests. Build an installable package and check it in a clean environment.

For a pure Python wheel, `python <skill>/scripts/check_wheel.py PACKAGE.whl --source-root src --output wheel-check.json` checks RECORD integrity and compares runtime Python files with the selected source import root. It can catch stale builds and leftover old package names; it does not establish that the source was tested, compare data to source or verify native builds. Test the exact wheel in a new environment outside the source import path. Exclude stale build products, vendor installers/models and private host paths from the source release. Verify uploaded attachments by downloading and hashing them, and compare remote release copies with the same checksum list when those delivery channels are requested.

Keep browser profiles, authenticated storage state, raw network recordings and user documents out of release archives. Separate clean-environment installation checks from real application tests: a disposable Python environment can prove packaging while the actual desktop program remains an external prerequisite. State that prerequisite and the exact tested host instead of claiming the archive is self-contained.

Report local results separately from configured CI: adding a workflow is not evidence that all matrix platforms passed. Make any unsupported platforms and omitted operating modes visible. A generated readiness probe is not a working conversion.

Summarize each requested capability as discovered, implemented, verified or blocked. A successful small operation proves that operation on the recorded environment; it does not establish arbitrary software conversion or full coverage of the application.
