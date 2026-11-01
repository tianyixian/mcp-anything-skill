import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from lammps_mcp.core import TERMINAL, Config, Jobs


class FakeJobs(Jobs):
    def command(self):
        return [sys.executable, str(Path(__file__).with_name("fake_engine.py"))]


@pytest.fixture
def jobs(tmp_path):
    return FakeJobs(Config(tmp_path / "workspace", allow_trusted=True))


def wait(jobs, job_id, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = jobs.status(job_id)
        if state["status"] in TERMINAL:
            return jobs.result(job_id)
        time.sleep(0.05)
    pytest.fail(f"Job did not finish: {jobs.status(job_id)}")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cells": 9},
        {"steps": -1},
        {"steps": True},
        {"temperature": float("nan")},
        {"density": float("inf")},
        {"timeout_seconds": 0},
        {"seed": 0},
    ],
)
def test_numeric_template_rejects_invalid(jobs, kwargs):
    with pytest.raises(ValueError):
        jobs.run_lj(**kwargs)
    assert list(jobs.jobs.iterdir()) == []


def test_trusted_script_opt_in(tmp_path):
    service = Jobs(Config(tmp_path))
    with pytest.raises(ValueError, match="disabled"):
        service.submit("shell rm -rf anything")


def test_missing_executable_probe(tmp_path):
    service = Jobs(Config(tmp_path, executable=str(tmp_path / "missing-lmp.exe")))
    assert service.probe()["available"] is False


def test_supervisor_requirement_is_explicit(tmp_path):
    service = Jobs(Config(tmp_path, use_supervisor=True))
    with pytest.raises(ValueError, match="supervisor"):
        service.run_lj()


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a/b", "a\\b", "CON", "input.in", "RESULT.JSON"])
def test_bundle_paths_rejected(jobs, name):
    with pytest.raises(ValueError):
        jobs.submit("ok", {name: "data"})


def test_success_durable_and_artifact_pagination(jobs):
    submitted = jobs.submit("ok")
    # A fresh service instance retrieves a worker launched by the first instance.
    restarted = Jobs(jobs.config)
    result = wait(restarted, submitted["job_id"])
    assert result["status"] == "succeeded", result
    assert result["exit_code"] == 0
    assert result["summary"]["created_atoms"] == 32
    assert result["summary"]["last"]["Step"] == 10
    assert result["input_sha256"] == submitted["input_sha256"]
    page = restarted.read_artifact(submitted["job_id"], "stdout.txt", max_bytes=7)
    assert page["next_offset"] == 7 and page["truncated"]
    assert "command" not in result


def test_failure_is_not_success(jobs):
    result = wait(jobs, jobs.submit("fail")["job_id"])
    assert result["status"] == "failed" and result["exit_code"] == 7
    assert "intentional fixture failure" in result["stderr_tail"]


def test_timeout_owned_by_worker(jobs):
    submitted = jobs.submit("sleep", timeout_seconds=1)
    result = wait(Jobs(jobs.config), submitted["job_id"])
    assert result["status"] == "timed_out"
    assert result["duration_seconds"] < 10


def test_cancel_and_parallel_limit(jobs):
    service = FakeJobs(replace(jobs.config, max_parallel=1))
    submitted = service.submit("sleep")
    try:
        with pytest.raises(ValueError, match="Parallel"):
            service.submit("ok")
        assert service.cancel(submitted["job_id"])["cancel_requested"]
        assert wait(service, submitted["job_id"])["status"] == "cancelled"
        assert not service.cancel(submitted["job_id"])["cancel_requested"]
    finally:
        service.cancel(submitted["job_id"])


def test_output_cap(jobs):
    service = FakeJobs(replace(jobs.config, max_output_bytes=1024))
    result = wait(service, service.submit("flood")["job_id"])
    assert result["status"] == "output_limit"
    assert result["captured_output_bytes"] <= 1024
    assert len(result["stdout_tail"].encode()) <= 1024


def test_artifact_traversal_and_symlinks(jobs, tmp_path):
    submitted = jobs.submit("ok")
    wait(jobs, submitted["job_id"])
    with pytest.raises(ValueError):
        jobs.read_artifact(submitted["job_id"], "../outside")
    with pytest.raises(ValueError):
        jobs.status("../../outside")
    with pytest.raises(ValueError):
        jobs.read_artifact(submitted["job_id"], "job.json")
    with pytest.raises(ValueError):
        jobs.read_artifact(submitted["job_id"], "Job.JSON")
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    link = jobs.directory(submitted["job_id"]) / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    with pytest.raises(ValueError, match="Symlink"):
        jobs.read_artifact(submitted["job_id"], "linked.txt")


def test_stale_worker_report(jobs):
    submitted = jobs.submit("ok")
    wait(jobs, submitted["job_id"])
    directory = jobs.directory(submitted["job_id"])
    (directory / "result.json").unlink()
    (directory / "state.json").write_text(
        json.dumps({"job_id": submitted["job_id"], "status": "running", "heartbeat_at": 1})
    )
    assert jobs.status(submitted["job_id"])["status"] == "stale"
    with pytest.raises(ValueError, match="stale"):
        jobs.result(submitted["job_id"])


def test_workspace_symlink_rejected(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    with pytest.raises(ValueError):
        Jobs(Config(link))


def test_windows_junction_rejected(tmp_path):
    import os
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows junction behavior")
    target = tmp_path / "target"
    target.mkdir()
    junction = tmp_path / "junction"
    result = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(junction), str(target)], capture_output=True)
    if result.returncode:
        pytest.skip("OS does not permit junction creation")
    try:
        with pytest.raises(ValueError, match="junction"):
            Jobs(Config(junction))
    finally:
        junction.rmdir()


def test_contended_submission_lock_waits_without_reading_locked_byte(tmp_path):
    import subprocess
    from lammps_mcp.core import submission_lock

    command = [sys.executable, "-c", "from pathlib import Path; import sys; from lammps_mcp.core import submission_lock; print('ready', flush=True); ctx=submission_lock(Path(sys.argv[1])); ctx.__enter__(); print('acquired', flush=True); ctx.__exit__(None,None,None)", str(tmp_path)]
    with submission_lock(tmp_path):
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert child.stdout.readline().strip() == "ready"
        time.sleep(0.2)
        assert child.poll() is None
    stdout, stderr = child.communicate(timeout=10)
    assert child.returncode == 0, stderr
    assert "acquired" in stdout
