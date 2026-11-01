"""Local job lifecycle and bounded file access. This is not an OS sandbox."""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

TERMINAL = {"succeeded", "failed", "timed_out", "cancelled", "output_limit"}
JOB_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
RESERVED = {
    "input.in",
    "stdout.txt",
    "stderr.txt",
    "log.lammps",
    "job.json",
    "state.json",
    "result.json",
    "cancel.request",
    "engine-info.json",
}
MAX_INPUT = 1024 * 1024
MAX_BUNDLE = 4 * 1024 * 1024
MAX_READ = 65536


def no_links(path: Path) -> Path:
    """Reject symlinks/junctions in every existing component, including ancestors."""
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Symlinks and directory junctions are not supported")
        if os.name == "nt" and part.exists():
            attributes = getattr(part.lstat(), "st_file_attributes", 0)
            if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("Symlinks and directory junctions are not supported")
    return path


def read_json(path: Path) -> dict:
    no_links(path)
    if path.stat().st_size > MAX_BUNDLE + MAX_INPUT:
        raise ValueError("Job metadata exceeds size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Invalid job metadata")
    return value


def atomic_json(path: Path, value: dict) -> None:
    no_links(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.chmod(temporary, 0o600)
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                # Windows readers/antivirus can briefly hold the old file without delete sharing.
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)


def bounded_integer(value: int, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def bounded_number(value: float, minimum: float, maximum: float, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{name} must be finite and from {minimum} to {maximum}")
    return float(value)


def filename(value: str) -> str:
    if not isinstance(value, str) or not FILENAME.fullmatch(value) or value.endswith("."):
        raise ValueError("Use a plain filename of at most 100 ASCII letters, digits, dots, underscores or hyphens")
    if value.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        raise ValueError("Reserved operating-system filename")
    return value


@dataclass(frozen=True)
class Config:
    workspace: Path
    executable: str | None = None
    allow_trusted: bool = False
    max_parallel: int = 2
    max_output_bytes: int = 16 * 1024 * 1024
    use_supervisor: bool = False

    @classmethod
    def from_env(cls) -> Config:
        raw = os.environ.get("LAMMPS_MCP_WORKSPACE")
        if not raw or not Path(raw).is_absolute():
            raise ValueError("Set LAMMPS_MCP_WORKSPACE to an absolute local directory")
        return cls(
            Path(raw),
            os.environ.get("LAMMPS_EXECUTABLE") or None,
            os.environ.get("LAMMPS_ALLOW_TRUSTED_INPUT") == "1",
            bounded_integer(int(os.environ.get("LAMMPS_MAX_PARALLEL", "2")), 1, 32, "LAMMPS_MAX_PARALLEL"),
            use_supervisor=os.name == "nt" or os.environ.get("LAMMPS_USE_SUPERVISOR") == "1",
        )


@contextlib.contextmanager
def submission_lock(root: Path, lock_name: str = ".submit.lock", blocking: bool = True):
    path = no_links(root / lock_name)
    with path.open("a+b") as stream:
        # Windows byte-range locks also forbid reading the locked byte. Inspect
        # the file size rather than reading before acquiring the lock.
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def spawn_worker(directory: Path) -> None:
    options = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with open(os.devnull, "rb") as null_in, open(os.devnull, "wb") as null_out:
        subprocess.Popen(
            [sys.executable, "-m", "lammps_mcp.worker", str(directory)],
            stdin=null_in,
            stdout=null_out,
            stderr=null_out,
            close_fds=True,
            env={**os.environ, "OMP_NUM_THREADS": "1"},
            **options,
        )


class Jobs:
    def __init__(self, config: Config):
        self.config = config
        self.root = no_links(config.workspace)
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = no_links(self.root / "jobs")
        self.jobs.mkdir(exist_ok=True)
        bounded_integer(config.max_parallel, 1, 32, "max_parallel")

    def directory(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise ValueError("Invalid job_id; use the UUID returned by submission")
        directory = no_links(self.jobs / job_id)
        if not directory.is_dir():
            raise ValueError("Unknown job_id")
        return directory

    def command(self) -> list[str]:
        if self.config.executable:
            path = Path(self.config.executable)
            if not path.is_absolute() or not path.is_file() or path.suffix.lower() in {".bat", ".cmd", ".ps1"}:
                raise ValueError("LAMMPS_EXECUTABLE must name an existing absolute native executable")
            return [str(path), "-in", "input.in", "-log", "none", "-nocite"]
        return [sys.executable, "-m", "lammps_mcp.engine", "input.in"]

    def probe(self) -> dict:
        try:
            command = self.command()
            if self.config.executable:
                command = [command[0], "-help"]
            else:
                command = [sys.executable, "-m", "lammps_mcp.engine", "--probe"]
            # LAMMPS help is bounded in normal supported releases. Keep the returned tail small.
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=15,
                env={**os.environ, "OMP_NUM_THREADS": "1"},
                check=False,
            )
            output = result.stdout.decode("utf-8", errors="replace")
            details = None
            if not self.config.executable and result.returncode == 0:
                details = json.loads(output)
            return {
                "available": result.returncode == 0,
                "backend": "executable" if self.config.executable else "python-library",
                "engine": details,
                "diagnostic": (result.stderr.decode("utf-8", errors="replace") or output)[-4096:],
                "trusted_input_enabled": self.config.allow_trusted,
                "max_parallel": self.config.max_parallel,
                "max_output_bytes": self.config.max_output_bytes,
                "supervisor_required": self.config.use_supervisor,
                "supervisor_ready": self.supervisor_ready(),
                "note": "LAMMPS execution capability only; no claim of validated polymer Tg prediction.",
            }
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            return {"available": False, "diagnostic": str(error), "trusted_input_enabled": self.config.allow_trusted}

    def supervisor_ready(self) -> bool:
        try:
            heartbeat = read_json(self.root / ".supervisor.json")
            return 0 <= time.time() - heartbeat["heartbeat_at"] < 10
        except (OSError, ValueError, KeyError):
            return False

    def run_lj(
        self,
        cells: int = 4,
        steps: int = 100,
        temperature: float = 1.0,
        density: float = 0.8442,
        timestep: float = 0.005,
        seed: int = 87287,
        timeout_seconds: int = 60,
    ) -> dict:
        bounded_integer(cells, 2, 8, "cells")
        bounded_integer(steps, 0, 200000, "steps")
        bounded_integer(seed, 1, 900000000, "seed")
        temperature = bounded_number(temperature, 0.01, 10, "temperature")
        density = bounded_number(density, 0.1, 1.5, "density")
        timestep = bounded_number(timestep, 0.0001, 0.01, "timestep")
        script = f"""# Restricted Lennard-Jones smoke example; reduced LJ units, not a polymer Tg model.
units lj
atom_style atomic
boundary p p p
lattice fcc {density}
region box block 0 {cells} 0 {cells} 0 {cells}
create_box 1 box
create_atoms 1 box
mass 1 1.0
velocity all create {temperature} {seed} loop geom
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5
neighbor 0.3 bin
neigh_modify delay 0 every 1 check yes
timestep {timestep}
fix integrate all nve
thermo {max(1, steps // 10)}
thermo_style custom step temp pe ke etotal press vol density
run {steps}
"""
        return self._submit(
            script,
            {},
            timeout_seconds,
            "restricted-lj",
            {
                "cells": cells,
                "atoms": 4 * cells**3,
                "steps": steps,
                "temperature": temperature,
                "density": density,
                "timestep": timestep,
                "seed": seed,
            },
        )

    def submit(self, input_script: str, files: dict[str, str] | None = None, timeout_seconds: int = 900) -> dict:
        if not self.config.allow_trusted:
            raise ValueError(
                "Custom LAMMPS scripts are disabled. An operator must set LAMMPS_ALLOW_TRUSTED_INPUT=1; scripts then have the worker account's file and execution privileges."
            )
        return self._submit(input_script, files or {}, timeout_seconds, "trusted-input", {})

    def _submit(self, script: str, files: dict[str, str], timeout: int, mode: str, parameters: dict) -> dict:
        bounded_integer(timeout, 1, 86400, "timeout_seconds")
        if (
            not isinstance(script, str)
            or not script.strip()
            or "\x00" in script
            or len(script.encode("utf-8")) > MAX_INPUT
        ):
            raise ValueError("input_script must be nonempty UTF-8 text without NUL and at most 1 MiB")
        if not isinstance(files, dict) or len(files) > 20:
            raise ValueError("files must map at most 20 plain filenames to UTF-8 text")
        data = {"input.in": script.encode("utf-8")}
        for name, content in files.items():
            filename(name)
            if name.lower() in RESERVED or not isinstance(content, str) or "\x00" in content:
                raise ValueError("Reserved filename or invalid text attachment")
            data[name] = content.encode("utf-8")
        if len({name.lower() for name in data}) != len(data) or sum(map(len, data.values())) > MAX_BUNDLE:
            raise ValueError("Duplicate filename or bundle exceeds 4 MiB")
        command = self.command()
        if self.config.use_supervisor and not self.supervisor_ready():
            raise ValueError(
                "Start the independent supervisor first: python -m lammps_mcp.supervisor --workspace <same workspace>. Windows MCP clients can terminate all descendants on disconnect."
            )
        with submission_lock(self.root):
            active = sum(
                self.status(p.name)["status"] in {"queued", "running", "stale"}
                for p in self.jobs.iterdir()
                if JOB_ID.fullmatch(p.name) and p.is_dir()
            )
            if active >= self.config.max_parallel:
                raise ValueError(
                    f"Parallel job limit reached ({self.config.max_parallel}); wait for or cancel an active job"
                )
            job_id = str(uuid.uuid4())
            directory = no_links(self.jobs / job_id)
            directory.mkdir(mode=0o700)
            for name, contents in data.items():
                path = directory / name
                with path.open("xb") as stream:
                    stream.write(contents)
                os.chmod(path, 0o600)
            record = {
                "schema_version": 1,
                "job_id": job_id,
                "mode": mode,
                "parameters": parameters,
                "submitted_at": time.time(),
                "timeout_seconds": timeout,
                "command": command,
                "max_output_bytes": self.config.max_output_bytes,
                "input_sha256": {name: hashlib.sha256(contents).hexdigest() for name, contents in data.items()},
            }
            atomic_json(directory / "job.json", record)
            atomic_json(directory / "state.json", {"job_id": job_id, "status": "queued", "heartbeat_at": time.time()})
            try:
                if not self.config.use_supervisor:
                    atomic_json(directory / "state.json", {"job_id": job_id, "status": "queued",
                                                          "launched_at": time.time(), "heartbeat_at": time.time()})
                    spawn_worker(directory)
            except OSError as error:
                atomic_json(
                    directory / "result.json",
                    {**record, "status": "failed", "error": str(error), "finished_at": time.time()},
                )
                raise
        return {
            "job_id": job_id,
            "status": "queued",
            "mode": mode,
            "artifacts_directory": f"jobs/{job_id}",
            "input_sha256": record["input_sha256"],
            "next": "Poll job_status, then call job_result when terminal.",
        }

    def status(self, job_id: str) -> dict:
        directory = self.directory(job_id)
        if (directory / "result.json").exists():
            result = read_json(directory / "result.json")
            return {
                key: result.get(key)
                for key in ("job_id", "status", "submitted_at", "started_at", "finished_at", "exit_code", "error")
            }
        state = read_json(directory / "state.json")
        age = time.time() - state.get("heartbeat_at", 0)
        if age > 15:
            state = {
                **state,
                "status": "stale",
                "warning": "Worker heartbeat is over 15 seconds old. Completion is unknown; no success is inferred. Inspect local processes before manual cleanup.",
            }
        return {**state, "cancel_requested": (directory / "cancel.request").exists()}

    def result(self, job_id: str) -> dict:
        directory = self.directory(job_id)
        state = self.status(job_id)
        if state["status"] not in TERMINAL:
            raise ValueError(f"Job is {state['status']}; poll job_status before fetching a final result")
        result = read_json(directory / "result.json")
        # Do not expose the full command or host paths in routine result payloads.
        result.pop("command", None)
        result["artifacts"] = [
            {"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(directory.iterdir())
            if p.is_file()
            and not p.is_symlink()
            and FILENAME.fullmatch(p.name)
            and p.name not in {"job.json", "cancel.request"}
        ]
        result["stdout_tail"] = self._tail(directory / "stdout.txt")
        result["stderr_tail"] = self._tail(directory / "stderr.txt")
        return result

    @staticmethod
    def _tail(path: Path) -> str:
        if not path.exists():
            return ""
        no_links(path)
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 8192))
            return stream.read(8192).decode("utf-8", errors="replace")

    def cancel(self, job_id: str) -> dict:
        directory = self.directory(job_id)
        state = self.status(job_id)
        if state["status"] in TERMINAL:
            return {"job_id": job_id, "status": state["status"], "cancel_requested": False}
        path = no_links(directory / "cancel.request")
        with path.open("a", encoding="utf-8"):
            pass
        return {
            "job_id": job_id,
            "status": state["status"],
            "cancel_requested": True,
            "note": "The worker terminates its engine process tree; poll for terminal status.",
        }

    def read_artifact(self, job_id: str, name: str, offset: int = 0, max_bytes: int = 16384) -> dict:
        filename(name)
        if name.lower() in {"job.json", "cancel.request"} or name.lower().endswith(".tmp"):
            raise ValueError("Internal lifecycle files are not exposed as artifacts")
        bounded_integer(offset, 0, 2**53 - 1, "offset")
        bounded_integer(max_bytes, 1, MAX_READ, "max_bytes")
        path = no_links(self.directory(job_id) / name)
        if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("Artifact is not a regular file")
        size = path.stat().st_size
        with path.open("rb") as stream:
            stream.seek(offset)
            content = stream.read(max_bytes)
        return {
            "job_id": job_id,
            "name": name,
            "offset": offset,
            "next_offset": offset + len(content),
            "total_bytes": size,
            "truncated": offset + len(content) < size,
            "text": content.decode("utf-8", errors="replace"),
        }
