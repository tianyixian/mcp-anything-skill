# Accept the requested operation

Before implementing, retain every operation requested by the user and define its observable completion condition. Supporting checks may help an operation without completing it: reading a model, listing tools or checking an installation cannot verify a requested solve. Keep the upstream component/version, input identity, actual execution evidence, outcome assertions and remaining blocker with the relevant operation. Report the overall request incomplete while any requested operation remains unverified; partial delivery can still be useful.

For computation, assess the software's errors, expected result files and an operation-specific numerical assertion together. Record units and tolerances. Neither a zero exit code nor a completion banner establishes a successful solve: a vendor program can print `RUN COMPLETED` after reporting a license failure. Keep process outcome, application outcome and scientific acceptance separate. A fixture solver tests lifecycle behavior but cannot fill the real-solve row.

Identify the component that actually performed the operation. A configured command may be Python or a wrapper: its hash and a started-process flag identify that command, not the vendor engine. Retain engine/launcher version and signature/hash evidence separately when software identity matters. Correctly reporting a real license failure verifies that error path; the requested successful solve remains blocked until results and numerical assertions pass.

## Optional local completion gate

Use `assess_operations.py` when several operations or evidence files make completion easy to misread:

```sh
python <skill>/scripts/assess_operations.py operations.json --output operation-status.json
```

It does not invoke the application. It checks a local operation ledger against hash-pinned `check_mcp.py` reports and outcome artifacts. All paths in the ledger are relative to its directory; parent traversal, child links and Windows junctions are refused. Each referenced file is limited to 16 MiB; keep large native outputs separately and create a small reviewed result projection when needed.

The ledger has `schema_version: 1` and a nonempty `operations` array. IDs must be unique. Every row needs `id`, `request`, `acceptance` and `status`. Supported statuses are `not_started`, `discovered`, `implemented`, `blocked` and `verified`. A blocked row also needs `blocker`. For example, after a real model read but before a licensed solve is available:

```json
{
  "schema_version": 1,
  "operations": [
    {
      "id": "read_model",
      "request": "Read the model",
      "acceptance": "Vendor reader returns 104 nodes from the supplied input",
      "status": "verified",
      "upstream_component": "vendor-reader, tested version",
      "evidence_kind": "real",
      "checks": [
        {"path": "read-check.json", "sha256": "REPLACE_WITH_ACTUAL_SHA256", "cases": [0]}
      ],
      "artifacts": [
        {
          "path": "read-outcome.json",
          "sha256": "REPLACE_WITH_ACTUAL_SHA256",
          "assertions": [{"pointer": "/result/node_count", "equals": 104}]
        }
      ]
    },
    {
      "id": "solve_model",
      "request": "Solve the model",
      "acceptance": "Engine produces results and the expected displacement in stated units",
      "status": "blocked",
      "blocker": "No usable engine license on the tested host"
    }
  ]
}
```

Replace the illustrative hashes and observations with actual evidence. The result for this ledger is `complete: false`, with reading verified and solving blocked. Removing the blocked row would silently narrow the user's request; retain it until the user changes scope.

A row claiming `verified` qualifies only when:

- `evidence_kind` is `real` and `upstream_component` is stated. `fixture` and `analysis` remain unverified.
- Every referenced MCP report is successful and connected, with `validation_level: declared_calls_checked`. All selected case indices passed and at least one is a positive call. New reports include each case's `expect_error`; regenerate older reports that lack it. Discovery or negative-only checks cannot verify an operation.
- All referenced artifact hashes match and at least one outcome assertion passes. An artifact without `assertions` is checked for byte identity only, which is useful for a retained input, log or native result file. Assertions read JSON artifacts using RFC 6901 pointers, with exact `equals` or numeric `approx`, `atol` and `rtol`. Numerical comparison uses `abs(actual - approx) <= atol + rtol * abs(approx)`; tolerances default to zero. Approximate values must be representable as finite floats; overflowing arithmetic fails closed. Use exact `equals` for larger integer identities.

For example, a solve outcome projection can assert `/upstream_errors` equals `[]`, `/solver_executed` equals `true`, and `/displacement_m` approximately equals `5e-7` with a justified tolerance. Also pin the actual result file and inspect the relevant original logs. Mark shortened/sanitized projections as summaries with provenance to the retained originals; do not relabel them as canonical provider evidence.

Exit 0 means all listed operations qualify; exit 1 means at least one remains incomplete; exit 2 means invalid ledger/output. Output contains operation IDs and status/reason codes, omitting private request text, blockers, paths and actual values. The ledger and underlying artifacts may contain private information: review them separately before publishing.

The gate cannot determine whether a supplied artifact really came from the application, whether assertions test the requested behavior, or whether a requested operation was omitted. Those are review decisions. Hash consistency and a caller's `real` label are not independent proof of provenance. Keep that boundary explicit in the final report.
