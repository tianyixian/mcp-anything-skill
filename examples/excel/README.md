# Installed Excel → MCP

This example controls the installed Microsoft Excel application through its COM
automation interface. No Excel source checkout or REA installation is needed.
It is a deliberately small adapter for trusted **literal-data `.xlsx` files**:
create a workbook, read cells, and write into a new copy.

## Requirements and setup

- Windows, PowerShell 7 (`pwsh.exe` on PATH), and an installed, activated Microsoft Excel
  that starts successfully for the current user. A first-run Office dialog must
  be completed before unattended use.
- Python 3.11+ with `mcp==1.30.0`. The main repository's development environment
  already supplies it. No `pywin32` dependency is required.
- An existing, private scratch directory containing only trusted workbooks.

Run from a Python environment containing the MCP SDK:

```powershell
python examples/excel/server.py --workspace C:/work/excel-demo
```

The process communicates over MCP stdio. For client configuration, use your
Python executable as `command` and the absolute `server.py` path followed by
`--workspace` and your chosen directory as `args`. Keep that workspace fixed in
operator configuration. Tool calls accept plain filenames, not arbitrary paths.
If PowerShell 7 is not on PATH, add `--powershell` followed by its absolute
executable path. Windows PowerShell 5.1 is not the verified runtime: on the
acceptance host its Office interop binding failed, while PowerShell 7's COM
binding worked. The adapter does not modify Office or registry configuration.

Try the workflow in [USAGE.md](USAGE.md). To reproduce the real acceptance test:

```powershell
python examples/excel/verify.py
python -m pytest examples/excel -q
```

The verifier uses disposable workbooks, runs every tool through a separate MCP
process, verifies saved cell values, checks that source
bytes remain unchanged, and confirms owned Excel process cleanup. Tests skip
real execution on hosts without Excel; a skip is not evidence of compatibility.
The checked-in [validation.json](validation.json) is a real engine run, not a mock.

## Supported behavior

Each request starts its own hidden Excel instance. The worker records the
instance's process ID and start time, refuses a pre-existing Excel process,
disables events/macros/link updates, and opens source workbooks read-only.
Sources are never saved. Created or changed workbooks are staged and
published only after completion; existing outputs are never overwritten.
Normal and timeout cleanup targets only that owned process identity.

The worker is a fixed local PowerShell script. Requests arrive as JSON data;
tool callers cannot supply PowerShell, VBA, formulas, shell commands, arbitrary
COM calls, or executable paths. Text beginning with `=` is written as text.

Inputs are limited to 5 MiB `.xlsx` files and bounded ZIP contents. Formula
workbooks, macros, embedded objects, external-link parts and connections are
outside this example and refused. These checks are not a sandbox for malicious
Office files. Do not place adversarial files in this workspace.

At most 100 cells are read per request within `A1:Z1000`; writes are
rectangles of at most 10×10 cells. Text input is limited to 256 characters and
512 UTF-8 bytes per cell. Read text is clipped to at most 256 UTF-16 code units,
without splitting surrogate pairs, and clipping is reported. Each operation has a 45-second
worker deadline. A timeout without a recorded process identity is reported as
unconfirmed cleanup; the adapter never kills another Excel process to guess.

This is a Windows desktop-interface example, not cross-platform Excel support.
It does not cover formulas, charts, macros, arbitrary workbooks, concurrent
workspace modification, or remote multi-user deployment. Microsoft Excel is
installed and licensed separately and is not included in the archive.

PDF export is not exposed. A development probe failed on this host's print-layout
backend and subsequently timed out; the worker's recorded process was closed.
No printer configuration was changed. That attempted operation is not part of
the successful acceptance claim.
