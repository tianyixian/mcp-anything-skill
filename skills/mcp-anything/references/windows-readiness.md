# Windows application readiness

An executable found on Windows is a candidate, not a runnable software interface. Before implementing or claiming an adapter, establish that the supplied installation is complete enough for the requested operation.

## Readiness gate

Record these checks for the exact product build and host:

1. **Installation completion:** confirm that the installer finished successfully and that all required volumes/components were supplied. A partially copied directory, an interrupted installer, or an extracted private payload is evidence of a candidate only. Do not infer that a missing main program means the vendor product has no interface.
2. **Actual entry point:** identify the supported main application, launcher and underlying engine separately. Keep the absolute path, version/build, signature or hash and source of each executable. A wrapper or launcher hash identifies the wrapper; it does not identify the vendor engine it may start.
3. **Dependency closure:** launch the supported entry point in the intended working directory and capture loader failures, exit status and relevant stderr/log output. Missing DLL or runtime errors such as Windows `0xC0000135` are `missing_runtime_dependency`, not a successful interface check. Follow the vendor dependency/license chain before trying a different extracted binary.
4. **Elevation and session:** test under the intended user context. Record whether the path requires UAC/admin elevation, an interactive desktop, a service, a license server or a user profile. An executable that only starts after an unplanned elevation is not ready for unattended MCP use; expose the prerequisite or keep the operation blocked.
5. **Input contract:** for a multi-file project, retain the vendor manifest or companion-file list and record each file's role: project, intermediate, final solver input or result. Confirm the format and version through vendor documentation, help output or an actual parser. A file extension, existing path, sample-file status or renamed file does not prove that it is a valid solver input.
6. **Small valid input:** use the smallest authorized input that exercises the requested operation. Starting a solver with no input, a malformed file or a missing project demonstrates only invocation/error handling. If the upstream reports `input_format_or_version_failure`, classify it as a preflight/input-contract blocker; retain the command, exit status, stderr/log and input hashes, and do not report `solver_executed` or a solve result.
7. **Result acceptance:** check the vendor error channel, expected result files and operation-specific values together. A process that starts, prints a completion banner, or returns a launcher status does not prove that the upstream operation completed.

Use explicit statuses:

| Status | Meaning |
| --- | --- |
| `candidate` | Files or a launcher were found; installation or runtime is not established. |
| `launcher_only` | A wrapper starts or is identified, but its dependency chain or vendor engine is not ready. |
| `runtime_ready` | The supported entry point launches under the recorded context and accepts the minimal valid input path; requested operation still needs its own result check. |
| `operation_verified` | The actual MCP call produced the checked vendor state, artifact or numerical result. |
| `blocked` | A named prerequisite such as incomplete installation, missing DLL, UAC, license or valid input prevents the requested operation. |

For native dependencies, record each DLL/runtime/license component's source, version, architecture and signature/hash. Missing components such as vendor support libraries or crypto/cURL runtimes remain `blocked`; do not fill the gap with random DLLs, patches, different-architecture files or unverified private payloads. Do not silently substitute a binary from a temporary extraction directory, skip the installer, use a patch, or run as administrator just to turn a failed readiness check into a pass. If a vendor launcher and a lower-level solver behave differently, retain both observations and report the lower-level invocation as a separate diagnostic path.

## Evidence record

At minimum retain:

```json
{
  "platform": "Windows",
  "installation_status": "complete|partial|unknown",
  "entry_points": [
    {"role": "launcher|application|engine", "path": "...", "version": "...", "hash": "...", "tested": true}
  ],
  "runtime_context": {"user": "standard|administrator", "uac": "required|not_required|unknown", "interactive": true},
  "dependency_status": "ready|missing|unknown",
  "minimal_input": {"path": "...", "valid": true},
  "operation_status": "runtime_ready|operation_verified|blocked",
  "blocker": "..."
}
```

Keep private paths and license details out of public archives; retain sanitized identifiers and hashes when they are needed to explain provenance.
