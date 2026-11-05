# Discover a software control surface

Resolve the user's target and task before choosing an execution mechanism. GitHub is one possible source of evidence; an installed application, executable or website can be enough.

## Inspect the supplied target

The helper creates a bounded, nonexecuting inventory and suggests candidate routes:

```bash
python <skill>/scripts/discover_target.py ffmpeg --kind command --task "inspect media duration" --output discovery.json
python <skill>/scripts/discover_target.py /absolute/path/to/application --kind path --output discovery.json
python <skill>/scripts/discover_target.py https://example.com/app --kind url --output discovery.json
```

The helper does not launch programs, fetch websites, log in, or establish that a capability works. Its candidates still need inspection and a real test. A display name such as “Microsoft Excel” may not resolve through `PATH`; consult the platform's application registration or the user's supplied installation. Report ambiguity instead of selecting a similarly named executable. Do not expand a missing name into an unrestricted whole-disk search.

| Target | Useful evidence | What remains unproven |
| --- | --- | --- |
| Command or executable | Resolved executable, vendor help/documentation, installed version | That its flags perform the requested task and its dependencies work |
| Installation directory | Launchers, documentation, plugin/script interfaces, runtime markers | A marker identifies a candidate family, not an executable API |
| Website | Intended origin, existing MCP/API documentation, user session, observed workflow | An endpoint seen once may have state, authentication or ordering requirements |
| Library/database | Package/driver version, callable API/schema, representative input | Runtime behavior, access limits and result correctness |
| Source repository | Documented public entry points, build metadata, examples, commit | Source presence does not prove installation or operation |

For a known executable, inspect documented help/version options before invoking them. Record actual output when execution is appropriate; a filename alone does not identify its version. For a source checkout, use `inspect_repo.py` and normal source tools. For unknown packaged software, REA can provide additional observations as described in [REA investigation](rea.md).

For large installers or multi-volume media, locate the vendor manifest or package index before treating an outer executable as the product. Record which volumes and nested payloads were supplied, inspected or left unopened, with hashes for the components that support the chosen route. An extractor may identify only an embedded runtime; that does not establish that the product lacks a solver or API. Follow manifest entries to the actual launcher, engine and representative data. A small version-specific static extraction helper is appropriate when ordinary tools cannot expose the relevant payload; retain its bounds and evidence rather than generalizing it to other installer versions.

## Choose the least fragile route that completes the task

1. Reuse a suitable existing MCP server.
2. Select a supported API, CLI, library, plugin, scripting bridge or OS automation interface.
3. Use browser/desktop automation for a task that needs the user interface. Prefer semantic element identities and explicit state checks to screen coordinates.
4. Investigate unresolved packaged/runtime behavior with appropriate analysis tools. Use findings to implement an execution route; stop with a concrete blocker when no usable route has been established.

The sequence is a preference, not a demand to exhaust every route. A user-selected interface or a known working integration can settle the choice immediately.

Before creating an adapter, check the vendor's current MCP offerings and relevant package registries. Record the candidate's release/version, supported operations, runtime requirements, and whether it covers the user's operation; tool discovery or an installation-status query does not establish computation support. Reuse it when suitable, or explain the specific missing operation a new adapter supplies. Check the proposed distribution name and executable entry points against official and installed packages so the new adapter cannot shadow them. Python distribution names normalize case and punctuation, so changing only hyphens to underscores does not create a distinct name.

Validate candidates in separate environments when dependency ranges conflict. Record the interpreter, resolved MCP SDK and server versions, and run a compatible client/checker there; a Python SDK field-name change is a client compatibility issue until shown otherwise. Do not upgrade an existing adapter's runtime merely to inspect an official candidate, or infer compatibility from matching protocol names alone.

Before implementation, retain a small decision record: target identity, requested operation, chosen route, supporting observations, missing prerequisites, and the result that would demonstrate success. Distinguish “this installation contains Electron files” from “this version exposes an IPC method we can call”. Distinguish “a request appeared in a recording” from “we can make an authenticated request and verify its live effect”.

Use the [adapter contract](adapter-contract.md) to turn the selected route into a bounded business operation. Keep discovered, implemented and verified capabilities separate in the delivery report.
