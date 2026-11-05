# Adapter contract

Record these decisions before implementation; scale the detail to the software.

| Decision | Required evidence |
| --- | --- |
| Target | Software name, installed build or service revision, OS; repository/commit when available; relevant license and interface |
| Capability | Each user-requested operation, its completion condition, and excluded operations with reason |
| Route | Existing MCP, library, CLI, API, database, desktop scripting/automation or UI; observations supporting this choice |
| Status | Discovered candidate, implemented execution path, verified real outcome, or blocked with the missing condition |
| Input | Types, ranges, units, file format, optional defaults; no invented upstream arguments |
| Output | Structured result, artifact names, process exit separately from application/domain outcome, provenance |
| Dependencies | Runtime requirements separately from setup/investigation tools; whether REA is actually needed during execution |
| Execution | Operator configuration, working directory, authenticated session, trust boundary |
| Failure | Missing dependency, malformed input, upstream failure, timeout, cancellation |
| Lifecycle | Process/browser/document ownership; concurrency; synchronous duration or async jobs; restart and login recovery |
| Test | Real upstream component invoked, input/output evidence and meaningful assertions for each requested operation; relevant negative cases |

Library calls can corrupt stdio if native output reaches stdout; isolate them. CLI execution uses an argument list with no shell. HTTP adapters use an operator-selected base URL and normal request timeouts; tokens remain runtime configuration.

For application automation, define which session and documents the adapter owns, which application state can change, and the postcondition that proves completion. Restrict the callable surface to named operations rather than arbitrary scripts, DOM evaluation or object-member dispatch. A lost response after a write is an unknown outcome until checked; do not automatically repeat it. Document shared-session serialization and headless/interactive requirements.

Jobs should have unique IDs and separate directories. Save immutable request metadata, input hashes, engine version, status and results. A server memory dictionary is not durable job storage. If jobs must survive client shutdown, test shutdown while the job is still running. A surviving process alone does not prove that timeout and result collection still work.

For persistent jobs, define who supervises the engine after an MCP disconnect and where clients recover status. A supervisor intended to outlive clients must have a lifecycle independent of their process tree. Cover the relevant boundaries: reconnect during execution, cancellation before start, a launcher exiting while owned children remain, and termination cleanup that still emits a heartbeat. Process ownership must be established at launch; a historical PID alone is insufficient authority to kill a process.

After a hard supervisor failure, distinguish a stale job record from the engine's actual state. Report an unknown engine outcome until checked, and avoid automatically replaying a possibly running computation. A zero process exit code proves only that exit condition: check the software's logs/results and the requested numerical or artifact postcondition before calling the operation verified. Reading a model with a genuine vendor library can verify reading while the requested solve remains implemented or blocked.

Inputs that are executable scripts require an explicit trust model. Restricting a wrapper filename does not restrict `include`, output paths, shell escapes or native extensions inside the software. A generated numeric-only template is a distinct, narrower interface. For untrusted scripts, use real OS isolation rather than describing a denylist as a sandbox.

Resource limits should be explicit. State whether output caps are sampled or hard limits, how stale workers are represented, and which deployment modes were tested.
