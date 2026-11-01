# Adapter contract

Record these decisions before implementation; scale the detail to the software.

| Decision | Required evidence |
| --- | --- |
| Upstream | Repository, immutable commit or release, license, relevant public interface |
| Capability | Exact operation exposed; excluded operations and reason |
| Input | Types, ranges, units, file format, optional defaults; no invented upstream arguments |
| Output | Structured result, artifact names, exit/solver status, provenance |
| Execution | Library/CLI/HTTP, operator configuration, working directory, trust boundary |
| Failure | Missing dependency, malformed input, upstream failure, timeout, cancellation |
| Lifecycle | Synchronous duration or async submit/status/result/cancel; restart behavior |
| Test | Small real case with a meaningful assertion, protocol call, negative cases |

Library calls can corrupt stdio if native output reaches stdout; isolate them. CLI execution uses an argument list with no shell. HTTP adapters use an operator-selected base URL and normal request timeouts; tokens remain runtime configuration.

Jobs should have unique IDs and separate directories. Save immutable request metadata, input hashes, engine version, status and results. A server memory dictionary is not durable job storage. If jobs must survive client shutdown, test shutdown while the job is still running. A surviving process alone does not prove that timeout and result collection still work.

Inputs that are executable scripts require an explicit trust model. Restricting a wrapper filename does not restrict `include`, output paths, shell escapes or native extensions inside the software. A generated numeric-only template is a distinct, narrower interface. For untrusted scripts, use real OS isolation rather than describing a denylist as a sandbox.

Resource limits should be explicit. State whether output caps are sampled or hard limits, how stale workers are represented, and which deployment modes were tested.
