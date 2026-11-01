"""Run the LAMMPS library in a separate process, never inside MCP stdout."""

from __future__ import annotations

import importlib.metadata
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Expected --probe or an input filename", file=sys.stderr)
        return 2
    try:
        from lammps import lammps

        probe = sys.argv[1] == "--probe"
        options = ["-log", "none", "-nocite"]
        if probe:
            options += ["-screen", "none"]
        simulation = lammps(cmdargs=options)
        info = {
            "version": simulation.version(),
            "backend": "python-library",
            "distribution_version": importlib.metadata.version("lammps"),
        }
        try:
            if probe:
                print(json.dumps(info))
            else:
                Path("engine-info.json").write_text(json.dumps(info) + "\n", encoding="utf-8")
                simulation.file(sys.argv[1])
        finally:
            simulation.close()
        return 0
    except Exception as error:  # noqa: BLE001 - isolate all native-library failure types from MCP
        print(f"LAMMPS engine failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
