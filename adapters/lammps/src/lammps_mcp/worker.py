"""Detached worker: lifetime, wall timeout and finalization outlive the MCP server."""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .core import JOB_ID, atomic_json, no_links, read_json


def terminate_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        if process.poll() is None:
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def thermo_summary(path: Path) -> dict:
    """Parse the bounded screen log without inferring scientific convergence."""
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    columns = None
    first = last = None
    count = 0
    for line in text.splitlines():
        words = line.split()
        if words and words[0] == "Step" and "Temp" in words:
            columns = words
            continue
        if columns and len(words) == len(columns):
            try:
                values = [float(word) for word in words]
                if any(not __import__("math").isfinite(value) for value in values):
                    continue
            except ValueError:
                continue
            row = dict(zip(columns, values))
            if first is None:
                first = row
            last = row
            count += 1
    atoms = re.search(r"Created\s+(\d+)\s+atoms", text)
    return {
        "thermo_rows": count,
        "first": first,
        "last": last,
        "created_atoms": int(atoms.group(1)) if atoms else None,
        "reported_total_wall_time": "Total wall time:" in text,
        "interpretation": "Engine execution evidence only. This is not a convergence or polymer Tg validation.",
    }


def run(directory: Path) -> int:
    directory = no_links(directory)
    if not JOB_ID.fullmatch(directory.name):
        raise ValueError("Invalid worker directory")
    record = read_json(directory / "job.json")
    if record["job_id"] != directory.name:
        raise ValueError("Job identity mismatch")
    started = time.time()
    state = {
        "job_id": record["job_id"],
        "status": "running",
        "submitted_at": record["submitted_at"],
        "started_at": started,
        "heartbeat_at": started,
        "worker_pid": os.getpid(),
    }
    process = None
    status, error, exit_code = "failed", None, None
    output_limit = threading.Event()
    output_lock = threading.Lock()
    output_bytes = [0]
    capture_errors: list[str] = []
    threads = []

    def capture(pipe, name):
        try:
            with no_links(directory / name).open("xb") as destination:
                while True:
                    chunk = pipe.read(65536)
                    if not chunk:
                        break
                    with output_lock:
                        remaining = max(0, record["max_output_bytes"] - output_bytes[0])
                        destination.write(chunk[:remaining])
                        destination.flush()
                        output_bytes[0] += min(remaining, len(chunk))
                        if len(chunk) > remaining:
                            output_limit.set()
        except Exception as exception:  # noqa: BLE001 - persist capture failures, never report success
            capture_errors.append(str(exception))
            output_limit.set()
        finally:
            pipe.close()

    try:
        for name, expected in record["input_sha256"].items():
            path = no_links(directory / name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Input changed after submission: {name}")
        atomic_json(directory / "state.json", state)
        if (directory / "cancel.request").exists():
            status = "cancelled"
        else:
            options = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(
                record["command"],
                cwd=directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                env={**os.environ, "OMP_NUM_THREADS": "1"},
                **options,
            )
            state["engine_pid"] = process.pid
            for pipe, name in [(process.stdout, "stdout.txt"), (process.stderr, "stderr.txt")]:
                thread = threading.Thread(target=capture, args=(pipe, name), daemon=True)
                thread.start()
                threads.append(thread)
            deadline = time.monotonic() + record["timeout_seconds"]
            next_heartbeat = 0.0
            while process.poll() is None:
                now = time.monotonic()
                if (directory / "cancel.request").exists():
                    status = "cancelled"
                    break
                if output_limit.is_set():
                    status = "output_limit"
                    error = "Captured stdout/stderr exceeded the configured byte limit"
                    break
                if now >= deadline:
                    status = "timed_out"
                    error = "Worker wall-clock deadline exceeded"
                    break
                if now >= next_heartbeat:
                    atomic_json(directory / "state.json", {**state, "heartbeat_at": time.time()})
                    next_heartbeat = now + 1
                time.sleep(0.05)
            else:
                status = "succeeded" if process.returncode == 0 else "failed"
            if process.poll() is None:
                terminate_tree(process)
            exit_code = process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=2)
            if output_limit.is_set() and status not in {"cancelled", "timed_out"}:
                status = "output_limit"
                error = "Captured stdout/stderr exceeded the configured byte limit"
            if capture_errors:
                status, error = "failed", "; ".join(capture_errors)
    except Exception as exception:  # noqa: BLE001 - worker boundary must record a final failure
        error = f"{type(exception).__name__}: {exception}"
        status = "failed"
        if process is not None and process.poll() is None:
            terminate_tree(process)
        if process is not None:
            exit_code = process.returncode
    finally:
        result = {
            **record,
            "status": status,
            "started_at": started,
            "finished_at": time.time(),
            "duration_seconds": time.time() - started,
            "exit_code": exit_code,
            "error": error,
            "worker_pid": os.getpid(),
            "captured_output_bytes": output_bytes[0],
        }
        result.pop("command", None)
        try:
            result["summary"] = thermo_summary(directory / "stdout.txt")
            engine_info = directory / "engine-info.json"
            banner = (
                re.search(
                    r"^LAMMPS[^\r\n]*",
                    (directory / "stdout.txt").read_text(encoding="utf-8", errors="replace"),
                    re.MULTILINE,
                )
                if (directory / "stdout.txt").exists()
                else None
            )
            result["engine"] = (
                read_json(engine_info)
                if engine_info.exists()
                else {"backend": "executable", "version": banner.group(0) if banner else None}
            )
        except Exception as exception:  # noqa: BLE001 - retain exit evidence if optional parsing fails
            result["summary_error"] = str(exception)
        atomic_json(directory / "result.json", result)
        atomic_json(directory / "state.json", {**state, "status": status, "heartbeat_at": time.time()})
    return 0 if status == "succeeded" else 1


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    return run(Path(sys.argv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
