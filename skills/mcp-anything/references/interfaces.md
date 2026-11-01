# Choosing an interface

Start from the user's task. Expose a few useful named operations with typed inputs and structured outputs. Do not mechanically export every function or CRUD endpoint. Read and write operations can warrant separate tools when their permissions differ. Retain an existing interface if it already works.

| Source | Prefer | Verify before implementing |
| --- | --- | --- |
| Python or other library | Documented public functions | Installed version, argument semantics, stdout behavior, thread/process safety |
| CLI program | An absolute executable plus an argument array | Actual help/version output, exit status, output format, timeout and process cleanup |
| HTTP service / OpenAPI | Documented operations via an HTTP client | Server URL, operation/path/verb, auth scope, paging, rate limits, redirects |
| Database | Driver with least-privilege credentials | Schema, connection mode, row/byte/time limits, parameter binding |

## Library

Keep MCP dependencies in an isolated environment. Install the reviewed version, call one real function directly, then expose it through MCP. Describe units and valid ranges explicitly. Convert returned objects into documented JSON values; a string containing JSON is not a typed result. A native library that writes to stdout or blocks indefinitely needs a child process so MCP framing and timeouts remain reliable.

## CLI

Use `subprocess` argument arrays with `shell=False`. Select the executable in operator configuration; do not accept an arbitrary executable or command string from the tool caller. Treat argument injection separately from shell injection: use the upstream end-of-options delimiter where supported, or reject option-like positional values. Limit working paths, execution time and captured output. Prefer machine-readable output over fragile text scraping. Record the real executable version. For long work, use durable submit/status/result/cancel tools rather than holding a single MCP request open.

## HTTP and OpenAPI

Use the spec as evidence of an interface, not proof of a working service. Check the requested operation against live documentation and one authorized real call. Keep credentials in runtime environment or a secret store; never serialize them in examples, error bodies or generated code. Fix the base URL at deployment time, constrain redirects, and do not let callers turn a fetch tool into arbitrary network access. Respect existing authorization for write operations. Set request timeouts and response bounds; retries of writes require upstream idempotency support. Test pagination and error responses relevant to the chosen operation.

OpenAPI, GraphQL and gRPC can guide manual adaptation, but the included helpers do not automatically translate those schemas. Report unsupported transports or inaccessible endpoints honestly.

## Database

Start read-only unless writes are requested. Prefer named operations such as table discovery, schema inspection and a bounded row preview over a general SQL executor. Bind values and quote validated identifiers; table names cannot be bound as value parameters. Use the database's actual read-only mode/role, not a regex that looks for SELECT. Bound rows, bytes and query duration independently. Do not assume every database file is trustworthy; virtual tables, extensions and oversized values can require additional restrictions.

## Local or shared transport

Use stdio when the client can start the program. Streamable HTTP is appropriate for a shared running service; it needs platform routing, authentication and a documented access model. Binding `0.0.0.0` does not produce a public URL. Host/Origin checks do not provide authentication or per-user data isolation. Verify a routed URL from a separate client before advertising it as shared access.
