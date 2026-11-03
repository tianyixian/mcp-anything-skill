# Choosing an interface

Start from the user's task. Expose a few useful named operations with typed inputs and structured outputs. Do not mechanically export every function or CRUD endpoint. Read and write operations can warrant separate tools when their permissions differ. Retain an existing interface if it already works.

| Source | Prefer | Verify before implementing |
| --- | --- | --- |
| Python or other library | Documented public functions | Installed version, argument semantics, stdout behavior, thread/process safety |
| CLI program | An absolute executable plus an argument array | Actual help/version output, exit status, output format, timeout and process cleanup |
| HTTP service / OpenAPI | Documented operations via an HTTP client | Server URL, operation/path/verb, auth scope, paging, rate limits, redirects |
| Database | Driver with least-privilege credentials | Schema, connection mode, row/byte/time limits, parameter binding |
| Installed desktop software | Vendor scripting/plugin API or OS automation bridge such as COM | Installed build, session requirements, object ownership, macro policy, saved output |
| Website workflow | Existing API, otherwise semantic browser automation | Intended origin, login/session lifecycle, selectors, observable completion and repeated calls |
| Desktop UI workflow | Accessibility/automation controls | Interactive desktop, control identities, dialogs, application version and output readback |

## Library

Keep MCP dependencies in an isolated environment. Install the reviewed version, call one real function directly, then expose it through MCP. Describe units and valid ranges explicitly. Convert returned objects into documented JSON values; a string containing JSON is not a typed result. A native library that writes to stdout or blocks indefinitely needs a child process so MCP framing and timeouts remain reliable.

## CLI

Use `subprocess` argument arrays with `shell=False`. Select the executable in operator configuration; do not accept an arbitrary executable or command string from the tool caller. Treat argument injection separately from shell injection: use the upstream end-of-options delimiter where supported, or reject option-like positional values. Limit working paths, execution time and captured output. Prefer machine-readable output over fragile text scraping. Record the real executable version. For long work, use durable submit/status/result/cancel tools rather than holding a single MCP request open.

## HTTP and OpenAPI

Use the spec as evidence of an interface, not proof of a working service. Check the requested operation against live documentation and one authorized real call. Keep credentials in runtime environment or a secret store; never serialize them in examples, error bodies or generated code. Fix the base URL at deployment time, constrain redirects, and do not let callers turn a fetch tool into arbitrary network access. Respect existing authorization for write operations. Set request timeouts and response bounds; retries of writes require upstream idempotency support. Test pagination and error responses relevant to the chosen operation.

OpenAPI, GraphQL and gRPC can guide manual adaptation, but the included helpers do not automatically translate those schemas. Report unsupported transports or inaccessible endpoints honestly.

## Database

Start read-only unless writes are requested. Prefer named operations such as table discovery, schema inspection and a bounded row preview over a general SQL executor. Bind values and quote validated identifiers; table names cannot be bound as value parameters. Use the database's actual read-only mode/role, not a regex that looks for SELECT. Bound rows, bytes and query duration independently. Do not assume every database file is trustworthy; virtual tables, extensions and oversized values can require additional restrictions.

## Installed desktop software

An installed application can expose automation without providing its source. Check vendor scripting, plugins, command-line switches and platform bridges before using its UI. A COM registration or scripting dictionary is a candidate interface; verify an operation on the installed version.

Expose bounded domain operations rather than unrestricted script evaluation or COM member dispatch. For example, take a workbook path, sheet and cell range for `read_cells`, and explicit destination/format for an export. Set limits on file sizes, selected ranges and returned values. Opening a document may execute macros, refresh links or trigger dialogs; configure the specific application's supported noninteractive policies and test their effect.

Create an owned application instance or explicitly attach to the selected user session. Close only documents and processes the adapter owns. Record whether it needs an interactive desktop or an already logged-in user; a successful desktop test does not prove a headless service works. Respect thread/apartment constraints of the automation bridge and serialize operations that share application state. Read back saved output to verify completion; an API return alone may precede a save or export.

## Browser workflows

Bind the adapter to the intended application origin and a configured browser/session. Keep authentication in runtime storage, separate from distributable examples. Explain how a session is established and how an expired login is reported. Do not turn discovery of a URL into permission to create accounts or change unrelated application data.

Build named operations from semantic selectors or a verified application API. Give each operation explicit preconditions, action steps and a completion condition. For example, an export should identify the report, wait for the completed download, and inspect its format/content. A screenshot or click acknowledgement alone does not establish success.

Wait for observable state rather than fixed sleeps. If a write times out, inspect the target's state before retrying; report an unknown outcome when the effect cannot be established. Record idempotency or duplicate prevention where available. Serialize operations sharing a page, avoid disrupting unrelated tabs, and release only owned browser resources. Treat recorded network responses as fixtures until an actual call demonstrates live operation. Changes to the site's UI or session policy require revalidation.

## Desktop UI workflows

Use accessibility/control identities where available and scope actions to the selected application's window. Coordinates may be a documented fallback for a tested layout, not a portability guarantee. A stable named tool should include navigation, expected dialogs, completion checks and recovery, rather than asking every caller to supply a click sequence.

Record the tested OS, application build, locale and display/session requirements when they affect targeting. Handle missing or ambiguous controls explicitly. Verify outputs through an independent observation such as reopening an exported file or reading the updated field. Avoid retrying uncertain writes. Only claim support for the tested workflows; shared UI state generally requires serial execution and may preclude unattended multi-user hosting.

## Local or shared transport

Use stdio when the client can start the program. Streamable HTTP is appropriate for a shared running service; it needs platform routing, authentication and a documented access model. Binding `0.0.0.0` does not produce a public URL. Host/Origin checks do not provide authentication or per-user data isolation. Verify a routed URL from a separate client before advertising it as shared access.
