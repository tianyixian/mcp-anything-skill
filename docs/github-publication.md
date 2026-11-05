# Publication and release

Repository: https://github.com/tianyixian/mcp-anything-skill

The converter is **MCP Anything**, installed as `mcp-anything`. The current project and skill release is 0.4.2; the unchanged LAMMPS adapter uses 0.2.0. Release notes and GitHub Actions results identify what has actually been published and tested.

## Repeatable release

1. Run the skill, adapter, example and packaging tests. Record real engine runs separately from skipped integrations and fixtures.
2. Run `python scripts/build_release.py --target skill --output dist` for the standalone skill. It does not require building or installing LAMMPS.
3. To include the adapter, run `python -m build adapters/lammps`, then `python scripts/build_release.py --target all --output dist`.
4. Inspect the staged files and release manifests. `.gitignore` and the archive allowlist exclude internal deployment notes, environments and runtime jobs; review is still needed for new files.
5. Push the reviewed source, inspect the actual CI results, and publish the version tag with ZIPs and `SHA256SUMS.txt`. Do not overwrite a published version's files when changing functionality; release a new version.

## License boundary

The original skill, adapter code and documentation use MIT. LAMMPS remains independently licensed under GPLv2. Its reviewed upstream `stable_22Jul2025_update4` resolves to `611ca3b7f8525ba802373b04f9e3d632d515f7e3`; the tested Python distribution is `2025.7.22.4.0`. Those are different provenance fields.

This repository does not bundle LAMMPS source, binaries, MPI libraries or force-field databases. An optional engine installation does not change its license. The SQLite example uses Python's documented standard library and its separately installed SQLite engine. Dependencies keep their original licenses. Any future redistribution or copying of upstream components must preserve their notices and meet their distribution requirements.

The independently developed `gabrielekarra/mcp-anything` project is credited in `docs/related-work.md`; no code or templates were copied.

## Scope of claims

This release provides an agent skill, executable helpers, a read-only SQLite example, and a LAMMPS adapter with retained real-engine evidence. The skill requires the agent to implement software-specific behavior. It does not promise universal one-click conversion, a comparative benchmark advantage, or scientific validation of material properties. Host-specific UI setup and every possible operating system are not implied by protocol tests.

Private chat transcripts, deployment addresses and original research data are not needed to install or evaluate this open-source project and do not belong in its release.
