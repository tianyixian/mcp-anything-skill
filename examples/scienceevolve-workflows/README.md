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

The catalog points to the three full workflow files in `workflows/`.
Import the matching file into a compatible ScienceEvolve runtime,
then copy that domain's `run-spec.template.json` and
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

## Official SDK compatibility

On 2026-11-06, all three public workflow files passed the unchanged official
`sdk/src/main-config.ts:loadMainWorkflowConfig` at ScienceEvolve commit
`7c51eb49a53fdcf620badf145c286e12b80e7d3e`. Seven agents, their instructions
and embedded Skills were preserved; invalid route targets were rejected.
The [public-file report](validation/official-sdk-validation.json) records the
SHA256 of each tested Git file (LF line endings). It was generated separately
from checks of the private handoff packages.

With the official CLI installed, run from this example directory:

```sh
scievolve workflow validate workflows/pvdf.workflow.json
scievolve workflow validate workflows/pi.workflow.json
scievolve workflow validate workflows/binder.workflow.json
```

The older `validation/workflow-validation.json` retains historical SCION-AR
Web/SDK results for earlier handoff files. Its hashes do not identify the
current public JSON. The legacy `validate_workflows.mjs` is not included here
and does not support the current official SDK layout. The Web project is now
[ScienceEvolve-server](https://github.com/OpenMOSS/ScienceEvolve-server).


