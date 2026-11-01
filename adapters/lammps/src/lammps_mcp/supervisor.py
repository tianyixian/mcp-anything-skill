"""Independent queue launcher, required on Windows to survive client tree cleanup.

Start this from an operator terminal/service BEFORE the MCP client, never as its child.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .core import JOB_ID, Config, Jobs, atomic_json, read_json, spawn_worker, submission_lock


def serve(workspace: Path) -> None:
    service = Jobs(Config(workspace))
    with submission_lock(service.root, ".supervisor.lock", blocking=False):
        while True:
            atomic_json(service.root / ".supervisor.json", {"pid": os.getpid(), "heartbeat_at": time.time()})
            with submission_lock(service.root):
                for directory in service.jobs.iterdir():
                    if not JOB_ID.fullmatch(directory.name) or not directory.is_dir():
                        continue
                    if (directory / "result.json").exists():
                        continue
                    state = read_json(directory / "state.json")
                    if state.get("status") != "queued" or state.get("launched_at"):
                        continue
                    atomic_json(
                        directory / "state.json", {**state, "launched_at": time.time(), "heartbeat_at": time.time()}
                    )
                    try:
                        spawn_worker(directory)
                    except OSError as error:
                        record = read_json(directory / "job.json")
                        record.pop("command", None)
                        atomic_json(
                            directory / "result.json",
                            {**record, "status": "failed", "error": str(error), "finished_at": time.time()},
                        )
            time.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=os.environ.get("LAMMPS_MCP_WORKSPACE"))
    args = parser.parse_args()
    if args.workspace is None or not args.workspace.is_absolute():
        parser.error("set --workspace or LAMMPS_MCP_WORKSPACE to an absolute directory")
    try:
        serve(args.workspace)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        print(f"Supervisor could not start or continue: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
