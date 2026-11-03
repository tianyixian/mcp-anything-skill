"""Software discovery must locate candidates without executing the target."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/discover_target.py"
spec = importlib.util.spec_from_file_location("discover_target", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_named_command_is_located_but_never_executed(tmp_path, monkeypatch):
    executable = tmp_path / "target.py"
    marker = tmp_path / "executed"
    executable.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    monkeypatch.setattr(module.shutil, "which", lambda name: str(executable))
    report = module.discover("fictional-app", kind="command", task="inspect data")
    assert report["locations"][0]["path"] == str(executable.resolve())
    assert not marker.exists()
    assert report["verified_operations"] == []
    assert not any(route["verified"] for route in report["interface_candidates"])


def test_unresolved_and_ambiguous_names_do_not_pick_a_program(monkeypatch):
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    monkeypatch.setattr(module, "registered_windows_apps", lambda name: [])
    assert module.discover("Unknown Application")["status"] == "needs_location"
    monkeypatch.setattr(module, "registered_windows_apps", lambda name: [{"path": "one"}, {"path": "two"}])
    report = module.discover("Unknown Application")
    assert report["status"] == "needs_selection"
    assert report["source_kind"] == "software_name"


def test_directory_inventory_records_candidates_and_omits_private_names(tmp_path):
    (tmp_path / "resources").mkdir()
    (tmp_path / "resources/app.asar").write_bytes(b"not an actual archive")
    (tmp_path / "app.exe").write_bytes(b"not a verified executable")
    (tmp_path / "secrets.txt").write_text("PRIVATE")
    (tmp_path / ".env").write_text("TOKEN=PRIVATE")
    (tmp_path / "package.json").write_text('{"scripts":{"postinstall":"do-not-run"}}')
    report = module.discover(str(tmp_path), kind="path")
    candidates = {item["path"]: item["kind"] for item in report["inventory"]["candidates"]}
    assert candidates["resources/app.asar"] == "electron_archive_candidate"
    assert candidates["app.exe"] == "executable_candidate"
    assert "PRIVATE" not in json.dumps(report)
    assert "do-not-run" not in json.dumps(report)
    assert report["verified_operations"] == []


def test_scan_and_depth_limits_are_observable(tmp_path):
    for i in range(20):
        (tmp_path / f"app-{i}.exe").touch()
    limited = module.discover(str(tmp_path), max_entries=5)["inventory"]
    assert limited["entries_examined"] == 5
    assert limited["partial"]
    directory = tmp_path / "nested"
    directory.mkdir()
    (directory / "hidden.exe").touch()
    shallow = module.discover(str(tmp_path), max_depth=0)["inventory"]
    assert shallow["partial"]
    assert not any(item["path"].endswith("hidden.exe") for item in shallow["candidates"])


def test_windows_batch_cli_is_retained_as_unverified_candidate(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/gradle.bat").write_text("@echo off\nexit /b 0\n")
    report = module.discover(str(tmp_path), task="Run the existing project test task")
    assert {"path": "bin/gradle.bat", "kind": "script_launcher_candidate"} in report["inventory"]["candidates"]
    assert not report["target_executed"]
    assert report["verified_operations"] == []


@pytest.mark.parametrize("target", ["https://u:p@example.com/", "https://example.com/?token=secret", "https://example.com/#secret", "file:///tmp/app", "https://example.com:invalid/"])
def test_credential_bearing_and_invalid_urls_are_rejected(target):
    with pytest.raises(ValueError):
        module.discover(target, kind="url")


def test_url_is_classified_without_fetching_or_claiming_reachability():
    report = module.discover("https://not-a-real-service.invalid/app")
    assert report["source_kind"] == "web_url"
    assert report["status"] == "candidate"
    assert not report["network_accessed"]
    assert {r["route"] for r in report["interface_candidates"]} == {"existing_mcp", "documented_api", "browser_automation"}
    assert module.discover("https://github.com/example/project")["source_kind"] == "repository_url"


def test_cli_preserves_existing_output(tmp_path):
    output = tmp_path / "report.json"
    output.write_text("existing")
    result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path), "--output", str(output)], capture_output=True)
    assert result.returncode != 0
    assert output.read_text() == "existing"


def test_child_symlink_is_not_followed(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "outside.exe").touch()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symbolic links requires OS permission")
    result = module.discover(str(root))["inventory"]
    assert result["links_omitted"] == 1
    assert result["candidates"] == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions only")
def test_child_junction_is_not_followed(tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "outside.exe").touch()
    junction = root / "linked"
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
    if made.returncode:
        pytest.skip("OS did not permit creating a test junction")
    try:
        report = module.discover(str(root))["inventory"]
        assert report["links_omitted"] == 1
        assert report["candidates"] == []
    finally:
        os.rmdir(junction)
