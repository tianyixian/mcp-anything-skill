# ScienceEvolve materials workflow examples

This example package contains three importable workflow configurations for
materials research:

- `pvdf`: PVDF wet spinning, evidence review, model review and experiment handoff.
- `pi`: functional polyimide evidence intake, candidate screening and model review.
- `binder`: self-healing binder, silicon-anode and sulfur-cathode handoff.

The package is configuration-first. It includes workflow JSON, domain prompts,
empty input templates, an offline preflight checker and configuration-only
validation records. It does not include experimental data, candidate libraries,
trained models, proprietary software, raw source documents or credentials.

## Run an offline preflight

Python 3.10 or newer is sufficient; the checker has no third-party dependency.
Run from this directory after creating the input files for the selected domain:

```bash
python scripts/preflight.py --project pvdf --workspace . --stage intake
python scripts/preflight.py --project pi --workspace . --stage analysis
python scripts/preflight.py --project binder --workspace . --stage intake
```

Exit code `2` means required inputs are missing, `1` means the input format is
invalid, and `0` means only the basic format checks completed. A successful
preflight is not a scientific result.

## Import and connect tools

The three short `*.workflow.json` files at the package root are public,
machine-readable capability contracts used by the catalog. Import the matching
full workflow from `workflows/` into a compatible ScienceEvolve/SCION-AR
runtime, then copy that domain's `run-spec.template.json` and
`input-columns.csv` into an actual project workspace. Configure the model and
available gateway in the target runtime. The workflows intentionally leave
`mcpServers` empty: literature search, PDF parsing, chemical identity lookup,
and optional simulation services must be discovered and tested in the target
runtime before use.

The existing MCP Anything LAMMPS adapter can run its documented small LJ
example. That evidence does not validate PI topology, force fields, Tg
prediction, PVDF spinning or binder performance.

See [`catalog.json`](catalog.json) for the machine-readable index and [the workflow catalog](../../docs/workflow-catalog.md) for capability status and claim boundaries. The `validation/` files record configuration and
preflight checks only; no Agent run or wet-lab experiment is implied.


