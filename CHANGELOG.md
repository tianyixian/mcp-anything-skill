# Changelog

## 0.4.4 — Public science workflow recipes

- Add sanitized ScienceEvolve recipes for PVDF wet spinning, functional PI screening and self-healing binder development.
- Publish a machine-readable capability map that separates discovered MCP surfaces, ordinary Python nodes, human handoffs and blocked simulation prerequisites.
- Record workflow import/preflight evidence without uploading original research attachments, internal deployment paths, credentials or commercial installers.

## 0.4.3 — Input contract evidence

- Require multi-file software projects to record file roles, formats and versions before treating an input as valid.
- Classify `input_format_or_version_failure` as a preflight blocker and preserve command, exit, logs and input hashes without claiming solver execution.
- Record native DLL/runtime/license provenance and reject random DLLs, patches, architecture substitutions and unverified payloads.

This release incorporates the YJK 8.1 official-sample boundary. The sample's `.pre` file is not promoted to a final IDS input by renaming.

## 0.4.2 — Windows runtime readiness

- Add a Windows readiness gate for partial installations, launcher/application/engine identity, dependency closure, UAC/session requirements and minimal valid inputs.
- Treat loader failures such as `0xC0000135`, unexpected administrator elevation and no-input solver exits as blockers or diagnostic evidence, not proof that an application is usable.
- Keep runtime readiness separate from requested-operation verification and prohibit silently substituting extracted binaries, patches or elevated execution.

This release incorporates the Windows installation findings from the YJK 8.1 case. It does not claim that YJK or any other commercial software is universally supported.

## 0.4.1 — Completion follows requested operations

- Define acceptance for each requested operation; keep unresolved operations visible even when protocol or supporting read checks pass. Add a local gate for hash-pinned call reports and outcome assertions, including numerical tolerances.
- Adapt the stdio checker to tested MCP SDK 1.30.0 and 2.3.0 model fields and pagination APIs. Report client compatibility separately from backend failures and keep conflicting dependency environments independent.
- Check official MCP coverage and package/entry names before creating adapters. Record large-installer layers, REA provider budgets and incomplete coverage accurately.
- Clarify persistent-job ownership, child-process cleanup, heartbeat and unknown outcomes. Completion banners or process exit cannot replace upstream-error, artifact and domain-result checks.
- Add a static pure-Python wheel/source check and run it in CI; retain original analysis evidence separately from sanitized summaries and verify delivered attachment hashes.

These changes improve the reusable skill. They do not claim an ANSYS solve or live access to another commercial application.

## 0.4.0 — Installed software and websites

- Accept software names, installation paths and websites alongside source repositories; choose an existing MCP, API, CLI or automation interface before UI automation.
- Add bounded software discovery through PATH, Windows App Paths and directory inventories. Discovery does not launch target software or fetch URLs, and reports only candidate interfaces.
- Add optional REA investigation guidance, keeping analysis dependencies separate from the generated adapter's actual runtime dependencies.
- Add runnable FFmpeg, Excel COM and browser examples, with real MCP verification and explicit environment requirements.
- Record discovered, implemented, verified and blocked operations separately; verify state/artifact changes after writes and document session ownership.

The LAMMPS adapter remains 0.2.0. Previously published archives are retained unchanged.

## 0.3.0 — MCP Anything Skill

- Rename the converter to `mcp-anything` and the public repository to `mcp-anything-skill`.
- Explain installation and usage in English and Chinese, including migration from `github-to-mcp`.
- Add interface guidance for libraries, CLI programs, documented APIs and databases; prefer an existing maintained MCP when suitable.
- Require a concise agent-facing usage guide with exact inputs and a tested recipe.
- Add a reusable MCP stdio checker and a runnable SQLite example.
- Package the skill independently of LAMMPS, with dedicated installation and validation documents.
- Credit the independently developed `gabrielekarra/mcp-anything` project accurately, including its current plugin/skill.

The LAMMPS adapter remains at 0.2.0. This release does not change its scientific model, public HTTP service or job-management behavior.

## 0.2.0 — LAMMPS HTTP delivery

Added Streamable HTTP to the LAMMPS adapter and validated actual engine execution and client reconnection through a platform gateway. Historical validation is retained in `docs/validation.md`.
