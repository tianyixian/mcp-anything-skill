# Optional software dependencies

No target application, browser, REA runtime, reverse-engineering engine or vendor SDK is bundled in the skill ZIP. The standalone skill's discovery helper uses Python's standard library. Its protocol checker and runnable Python examples additionally use the MCP Python SDK.

| Software | Role | Validation version / source | License and installation |
| --- | --- | --- | --- |
| REA | Optional investigation through MCP or CLI | `rea-agents` 6.8.0; https://github.com/morluto/rea | MIT for REA-authored code; its third-party tools retain their terms. Installed separately when needed. No REA code copied into this project. |
| FFmpeg / ffprobe | Audio example's execution backend | Installed FFmpeg 9.0.2; https://ffmpeg.org | Build-dependent LGPL/GPL terms; this project distributes no FFmpeg binary. |
| Microsoft Excel | Desktop example's execution backend through COM | Installed Windows desktop Excel; actual version in the example's acceptance record | Microsoft proprietary software; user supplies a licensed installation. No Office components included. |
| Playwright Core | Browser example's automation backend | Exact version in `examples/browser/package-lock.json`; https://playwright.dev | Apache-2.0; install separately with the example's npm lockfile. |
| Chrome / Edge / Chromium | Browser example's runtime | User-selected installed browser; actual version in acceptance record | Vendor/project terms; not bundled. The example uses its own session. |

The new adapters, test application, generated sample data and documentation are original project content under MIT. The notes test application is intentionally small and does not represent an independently maintained external website.

Historical LAMMPS, MPI, MCP SDK and SQLite notices remain in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Investigation dependencies and execution dependencies are listed separately in generated usage guides so users can install only what an adapter actually needs.
