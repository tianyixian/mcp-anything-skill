# Adapter contract

Record these decisions before implementation; scale the detail to the software.

| Decision | Required evidence |
| --- | --- |
| Target | Software name, installed build or service revision, OS; repository/commit when available; relevant license and interface |
| Capability | Exact operation exposed; excluded operations and reason |
| Route | Existing MCP, library, CLI, API, database, desktop scripting/automation or UI; observations supporting this choice |
| Status | Discovered candidate, implemented execution path, verified real outcome, or blocked with the missing condition |
| Input | Types, ranges, units, file format, optional defaults; no invented upstream arguments |
| Output | Structured result, artifact names, exit/solver status, provenance |
| Dependencies | Runtime requirements separately from setup/investigation tools; whether REA is actually needed during execution |
| Execution | Operator configuration, working directory, authenticated session, trust boundary |
| Failure | Missing dependency, malformed input, upstream failure, timeout, cancellation |
| Lifecycle | Process/browser/document ownership; concurrency; synchronous duration or async jobs; restart and login recovery |
| Test | Small real case with a meaningful assertion, protocol call, negative cases |

Library calls can corrupt stdio if native output reaches stdout; isolate them. CLI execution uses an argument list with no shell. HTTP adapters use an operator-selected base URL and normal request timeouts; tokens remain runtime configuration.

For application automation, define which session and documents the adapter owns, which application state can change, and the postcondition that proves completion. Restrict the callable surface to named operations rather than arbitrary scripts, DOM evaluation or object-member dispatch. A lost response after a write is an unknown outcome until checked; do not automatically repeat it. Document shared-session serialization and headless/interactive requirements.

Jobs should have unique IDs and separate directories. Save immutable request metadata, input hashes, engine version, status and results. A server memory dictionary is not durable job storage. If jobs must survive client shutdown, test shutdown while the job is still running. A surviving process alone does not prove that timeout and result collection still work.

Inputs that are executable scripts require an explicit trust model. Restricting a wrapper filename does not restrict `include`, output paths, shell escapes or native extensions inside the software. A generated numeric-only template is a distinct, narrower interface. For untrusted scripts, use real OS isolation rather than describing a denylist as a sandbox.

Resource limits should be explicit. State whether output caps are sampled or hard limits, how stale workers are represented, and which deployment modes were tested.
