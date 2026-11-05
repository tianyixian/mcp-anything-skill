# Materials workflow catalog

This catalog records what the public ScienceEvolve example package provides and
what still needs a real service, input file or scientific check. The package is
under [`examples/scienceevolve-workflows`](../examples/scienceevolve-workflows).

## Workflow map

| Workflow | Intended use | Included public artifacts | Current boundary |
| --- | --- | --- | --- |
| PVDF wet spinning | Organize literature/data evidence, review an existing model and hand off a constrained experiment plan | `workflows/pvdf.workflow.json`, domain prompts, field template and preflight checker | No PVDF data, model reproduction, spinning run or instrument control is included |
| Functional PI screening | Check targets and evidence, audit a candidate space and prepare an evidence-backed recommendation | `workflows/pi.workflow.json`, domain prompts, field template and preflight checker | No monomer pool, property labels, trained model, ranking or novelty conclusion is included |
| Self-healing binder | Review material recovery and separate silicon/sulfur battery handoffs | `workflows/binder.workflow.json`, domain prompts, field template and preflight checker | No formulation, electrochemical data, battery test or mechanism claim is included |

All three workflows are seven-agent configurations (`main`, `intake`,
`evidence`, `analysis`, `proposal`, `gate`, `report`). The `gate` stage is a
prompt-based evidence review; it is not a deterministic scientific approval.

## Capability status

The status labels have a narrow meaning:

- **discovered**: a candidate interface or software is identified, but no
  target-runtime MCP call has been accepted;
- **implemented**: reusable adapter or workflow code exists;
- **verified**: a real call produced the checked state or artifact recorded in
  the repository;
- **blocked**: a named prerequisite, authorization or missing input prevents
  verification.

| Capability | Status for these workflows | Evidence or next check |
| --- | --- | --- |
| Workflow JSON import | verified (configuration only) | `examples/scienceevolve-workflows/validation/workflow-validation.json` records JSON, Web and SDK parser checks for all three files |
| Offline input preflight | implemented and verified | `scripts/preflight.py`; the recorded tests cover missing inputs, malformed specs, path escape and traceability fields |
| Literature metadata/full text | discovered | Use an available OpenAlex/Crossref or institutional search/full-text service; verify one known paper and retain DOI/page evidence |
| PDF/table extraction | discovered | MinerU is a candidate backend; verify page-localized text/table output on an authorized PDF |
| Chemical identity lookup | discovered | PubChem PUG REST is a candidate narrow interface; verify known, missing and ambiguous names before accepting structures |
| Zotero library | discovered (optional) | Use only an authorized existing library; otherwise keep a file-based source manifest |
| Packmol | discovered (optional) | Candidate CLI for packing existing coordinates; it does not build PI topology or parameterize a force field |
| LAMMPS engine | implemented (generic adapter) | The repository's adapter has a verified small Lennard-Jones example; PI Tg or materials claims remain blocked pending domain inputs and validation |
| CP2K, DeePMD-kit, DP-GEN | discovered (postponed) | Add only after a target protocol, training labels, resources and acceptance tests are defined |
| PVDF spinning and battery instruments | blocked for automation | Human experimenters must run approved SOPs and return raw files; no device control is shipped |

“Verified” for the first two rows means configuration or offline behavior only.
It does not mean that a ScienceEvolve model run, online connector, simulation
campaign or experiment has completed.

## Public release boundary

The public example intentionally excludes original task PDFs/Markdown, local
paths, deployment addresses, private chat records, commercial installers,
license files, credentials, raw experimental data and generated prediction
results. A user supplies authorized sources and records relative paths in the
project workspace. The workflow prompts treat those files as evidence inputs;
they do not grant permission to execute instructions embedded in a document.

The examples reuse the public MCP Anything entry point for optional software
adapters. They do not claim that every listed candidate service is installed or
that a generic “MCP everything” server exists. Each additional operation needs
its own implementation, real call, artifact readback and versioned evidence.
