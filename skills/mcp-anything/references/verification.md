# Verification and release

Use the actual MCP SDK client to initialize a stdio session, list tools, validate their schemas, call at least one useful tool and inspect its structured result. Start the installed entry point rather than only calling Python functions in-process.

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

For a computation adapter, preserve a real minimal input and an output that demonstrates execution. Check a software-specific quantity (for example, LAMMPS atom count and final timestep), not only process exit code. Record software version and tolerances where numbers are compared. Scientific validity beyond the example is a separate claim.

Test relevant negative cases: malformed schema, missing engine, path escape, disabled trusted operations, upstream error, timeout and cancellation. Long-job adapters also need restart/reconnect coverage while a job is running. Use controlled fixture executables for deterministic failures when needed, and label fixture evidence explicitly.

Package only selected source, configuration examples, docs and tests. Exclude virtual environments, engine binaries unless intentionally licensed/distributed, private inputs, logs containing deployment details, credentials and full chat transcripts. Include licenses, dependency constraints, hashes and instructions to repeat tests. Build an installable package and check it in a clean environment.

Report local results separately from configured CI: adding a workflow is not evidence that all matrix platforms passed. Make any unsupported platforms and omitted operating modes visible. A generated readiness probe is not a working conversion.
