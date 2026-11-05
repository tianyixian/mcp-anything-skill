"""A passing read or protocol check must not complete a requested solve."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/assess_operations.py"
spec = importlib.util.spec_from_file_location("assess_operations", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def put(root, name, value):
    raw = json.dumps(value).encode() if not isinstance(value, bytes) else value
    (root / name).write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def ledger(tmp_path):
    check = put(tmp_path, "check.json", {
        "schema_version": 1, "ok": True, "protocol_connected": True,
        "validation_level": "declared_calls_checked",
        "cases": [{"index": 0, "ok": True, "expect_error": False}],
    })
    evidence = put(tmp_path, "read.json", {"result": {"nodes": 104, "solver_executed": False}})
    return {"schema_version": 1, "operations": [{
        "id": "read", "request": "Read the mesh", "acceptance": "104 nodes from the vendor reader",
        "status": "verified", "evidence_kind": "real", "upstream_component": "vendor-reader 1.0",
        "checks": [{**check, "cases": [0]}],
        "artifacts": [{**evidence, "assertions": [{"pointer": "/result/nodes", "equals": 104}]}],
    }, {
        "id": "solve", "request": "Solve the model", "acceptance": "Read back the expected displacement in meters",
        "status": "blocked", "blocker": "PRIVATE_LICENSE_LOCATION",
    }]}


def test_read_pass_does_not_complete_requested_solve(ledger, tmp_path):
    report = gate.assess(ledger, tmp_path)
    assert not report["complete"]
    assert report["operations"][0]["verified"]
    assert report["operations"][1] == {"id": "solve", "status": "blocked", "verified": False,
                                       "reason": "requested_operation_incomplete"}
    assert "PRIVATE_LICENSE_LOCATION" not in json.dumps(report)
    assert str(tmp_path) not in json.dumps(report)


def test_real_outcome_numeric_tolerance_and_required_artifact(ledger, tmp_path):
    solve = ledger["operations"][1]
    result = put(tmp_path, "solve.json", {"errors": [], "displacement_m": 5.00001e-7, "solver_executed": True})
    binary = put(tmp_path, "result.bin", b"independently retained result")
    solve.update(status="verified", evidence_kind="real", upstream_component="vendor-solver",
                 checks=copy.deepcopy(ledger["operations"][0]["checks"]), artifacts=[
                     binary, {**result, "assertions": [
                         {"pointer": "/errors", "equals": []},
                         {"pointer": "/solver_executed", "equals": True},
                         {"pointer": "/displacement_m", "approx": 5e-7, "rtol": 1e-4, "atol": 1e-12},
                     ]},
                 ])
    assert gate.assess(ledger, tmp_path)["complete"]
    (tmp_path / "result.bin").unlink()
    assert not gate.assess(ledger, tmp_path)["complete"]


def test_completed_banner_does_not_override_upstream_error(ledger, tmp_path):
    operation = ledger["operations"][0]
    operation["artifacts"] = [{**put(tmp_path, "failure.json", {
        "banner": "RUN COMPLETED", "process_exit_code": 7, "errors": ["LICENSE UNAVAILABLE"],
    }), "assertions": [{"pointer": "/errors", "equals": []}]}]
    report = gate.assess(ledger, tmp_path)
    assert report["operations"][0]["reason"] == "outcome_assertion_failed"
    assert not report["complete"]


@pytest.mark.parametrize("evidence_kind", ["fixture", "analysis"])
def test_fixture_or_analysis_cannot_verify_operation(ledger, tmp_path, evidence_kind):
    ledger["operations"][0]["evidence_kind"] = evidence_kind
    assert gate.assess(ledger, tmp_path)["operations"][0]["reason"] == "real_execution_evidence_required"


@pytest.mark.parametrize("change,reason", [
    ({"validation_level": "protocol_only"}, "evidence_invalid_or_check_failed"),
    ({"ok": False}, "evidence_invalid_or_check_failed"),
    ({"cases": [{"index": 0, "ok": True, "expect_error": True}]}, "positive_operation_call_required"),
    ({"cases": [{"index": 0, "ok": True}]}, "evidence_invalid_or_check_failed"),
    ({"cases": [{"index": 0, "ok": False, "expect_error": False}]}, "evidence_invalid_or_check_failed"),
])
def test_protocol_negative_and_failed_checks_do_not_qualify(ledger, tmp_path, change, reason):
    record = json.loads((tmp_path / "check.json").read_text())
    record.update(change)
    ledger["operations"][0]["checks"] = [{**put(tmp_path, "check.json", record), "cases": [0]}]
    assert gate.assess(ledger, tmp_path)["operations"][0]["reason"] == reason


def test_tampered_or_stale_artifact_is_incomplete(ledger, tmp_path):
    (tmp_path / "read.json").write_text('{"result":{"nodes":104}}\n')
    assert not gate.assess(ledger, tmp_path)["operations"][0]["verified"]


@pytest.mark.parametrize("name", ["../outside.json", "/outside.json", "C:/private.json", "sub\\outside.json"])
def test_outside_paths_are_refused(ledger, tmp_path, name):
    ledger["operations"][0]["artifacts"][0]["path"] = name
    assert not gate.assess(ledger, tmp_path)["operations"][0]["verified"]


def test_linked_evidence_refused(ledger, tmp_path):
    original = tmp_path / "read.json"
    moved = tmp_path / "canonical.json"
    original.rename(moved)
    try:
        original.symlink_to(moved)
    except OSError:
        pytest.skip("Windows account cannot create symlinks")
    assert not gate.assess(ledger, tmp_path)["operations"][0]["verified"]


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions only")
def test_junction_evidence_refused(ledger, tmp_path):
    external = tmp_path / "original"
    external.mkdir()
    (external / "read.json").write_bytes((tmp_path / "read.json").read_bytes())
    junction = tmp_path / "linked"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(external)], capture_output=True)
    if result.returncode:
        pytest.skip("No Windows junction support")
    try:
        ledger["operations"][0]["artifacts"][0]["path"] = "linked/read.json"
        assert not gate.assess(ledger, tmp_path)["operations"][0]["verified"]
    finally:
        os.rmdir(junction)


def test_duplicate_requests_empty_ledger_and_invalid_assertions_rejected(ledger):
    for changed in [
        {"schema_version": 1, "operations": []},
        {"schema_version": 1, "operations": [ledger["operations"][0]] * 2},
    ]:
        with pytest.raises(ValueError):
            gate.validate_ledger(changed)
    ledger["operations"][0]["artifacts"][0]["assertions"] = [{"pointer": "/x", "approx": 1, "atol": -1}]
    with pytest.raises(ValueError):
        gate.validate_ledger(ledger)


def test_hash_only_evidence_does_not_verify_outcome(ledger, tmp_path):
    del ledger["operations"][0]["artifacts"][0]["assertions"]
    assert gate.assess(ledger, tmp_path)["operations"][0]["reason"] == "outcome_assertion_required"


def test_json_pointer_arrays_escaping_and_boolean_number_distinction():
    record = {"a/b": [{"~value": True}]}
    assert gate.outcome_matches(record, {"pointer": "/a~1b/0/~0value", "equals": True})
    assert not gate.outcome_matches(record, {"pointer": "/a~1b/0/~0value", "equals": 1})
    assert not gate.outcome_matches(record, {"pointer": "/a~1b/0/~0value", "approx": 1})
    with pytest.raises(ValueError):
        gate.at_pointer(record, "/a~2b")


def test_overflowing_difference_or_tolerance_fails_closed():
    assert not gate.outcome_matches({"value": -1.7e308}, {"pointer": "/value", "approx": 1.7e308, "rtol": 1.1})
    assert not gate.outcome_matches({"value": 1.0}, {"pointer": "/value", "approx": 10**400})


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_ambiguous_or_nonfinite_json_rejected(raw):
    with pytest.raises(ValueError):
        gate.finite_json(raw)


def test_unrepresentable_approx_is_invalid_ledger():
    with pytest.raises(ValueError):
        gate.validate_ledger({"schema_version": 1, "operations": [{
            "id": "x", "request": "run", "acceptance": "result", "status": "verified",
            "evidence_kind": "real", "upstream_component": "engine",
            "artifacts": [{"path": "x.json", "sha256": "0" * 64,
                           "assertions": [{"pointer": "/x", "approx": 10**400}]}],
        }]})


def test_cli_exit_codes_and_report_preservation(ledger, tmp_path):
    plan = tmp_path / "operations.json"
    plan.write_text(json.dumps(ledger), encoding="utf-8")
    command = [sys.executable, str(SCRIPT), str(plan)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and not json.loads(result.stdout)["complete"]
    ledger["operations"].pop()
    plan.write_text(json.dumps(ledger), encoding="utf-8")
    assert subprocess.run(command, capture_output=True, timeout=10).returncode == 0
    existing = tmp_path / "summary.json"
    existing.write_text("keep this")
    result = subprocess.run([*command, "--output", str(existing)], capture_output=True, timeout=10)
    assert result.returncode == 2 and existing.read_text() == "keep this"
