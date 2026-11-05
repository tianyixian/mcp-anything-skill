"""Static wheel checks detect stale builds without importing source code."""
import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import warnings
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_wheel.py"
spec = importlib.util.spec_from_file_location("check_wheel", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
META = "demo_mcp-0.1.0.dist-info"


def record_for(files):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for name, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        writer.writerow([name, "sha256=" + digest, str(len(data))])
    writer.writerow([f"{META}/RECORD", "", ""])
    return stream.getvalue().encode()


def wheel_files(code=None):
    files = {
        "demo_mcp/__init__.py": b"raise RuntimeError('source must not be imported')\n",
        f"{META}/WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{META}/METADATA": b"Metadata-Version: 2.4\nName: demo-mcp\nVersion: 0.1.0\n",
        "demo_mcp/data.json": b'{"not_source": true}\n',
    }
    if code:
        files.update(code)
    files[f"{META}/RECORD"] = record_for(files)
    return files


def write_wheel(path, files, *, link=None, duplicate=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            info.filename = name  # retain unsafe original names on Windows
            info.compress_type = zipfile.ZIP_DEFLATED
            if name == link:
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, data)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(duplicate, files[duplicate])
    return path


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "src"
    (source / "demo_mcp").mkdir(parents=True)
    files = wheel_files()
    (source / "demo_mcp/__init__.py").write_bytes(files["demo_mcp/__init__.py"])
    wheel = write_wheel(tmp_path / "demo.whl", files)
    return source, wheel, files


def test_real_zip_record_and_source_pass_without_import_or_extract(sample, tmp_path):
    source, wheel, _files = sample
    report = checker.check_wheel(wheel, source)
    assert report["ok"] and report["record_verified"]
    assert report["source_python_count"] == report["wheel_python_count"] == 1
    assert str(tmp_path) not in json.dumps(report)
    # Source intentionally raises if imported; package data is not compared.
    assert not (tmp_path / "demo_mcp").exists()


def test_stale_renamed_missing_extra_and_changed_runtime_sources(sample):
    source, wheel, files = sample
    (source / "demo_mcp/__init__.py").write_bytes(b"# changed tested source\n")
    (source / "demo_mcp/new.py").write_bytes(b"# new module\n")
    files["demo_mcp/old_name.py"] = b"# stale renamed module\n"
    files[f"{META}/RECORD"] = record_for({key: data for key, data in files.items() if not key.endswith("/RECORD")})
    write_wheel(wheel, files)
    report = checker.check_wheel(wheel, source)
    assert report["failure"] == "python_source_mismatch"
    assert report["record_verified"] is True
    assert report["differences"] == {
        "missing": ["demo_mcp/new.py"], "extra": ["demo_mcp/old_name.py"],
        "changed": ["demo_mcp/__init__.py"],
    }


@pytest.mark.parametrize("changed", ["demo_mcp/__init__.py", "demo_mcp/data.json", f"{META}/METADATA"])
def test_record_detects_tampering_in_source_data_and_metadata(sample, changed):
    source, wheel, files = sample
    data = files[changed]
    files[changed] = b"X" + data[1:]
    write_wheel(wheel, files)
    report = checker.check_wheel(wheel, source)
    assert report["failure"] == "record_hash_mismatch"
    assert report["record_verified"] is False


def test_record_missing_member_and_bad_self_entry_fail(sample):
    source, wheel, files = sample
    files["unrecorded.txt"] = b"not listed"
    write_wheel(wheel, files)
    assert checker.check_wheel(wheel, source)["failure"] == "record_members_missing"
    files.pop("unrecorded.txt")
    files[f"{META}/RECORD"] = files[f"{META}/RECORD"].replace(
        f"{META}/RECORD,,".encode(), f"{META}/RECORD,sha256=bad,1".encode(),
    )
    write_wheel(wheel, files)
    assert checker.check_wheel(wheel, source)["failure"] == "invalid_record_self_entry"


def test_record_duplicate_and_size_mismatch_fail(sample):
    source, wheel, files = sample
    original = files[f"{META}/RECORD"]
    files[f"{META}/RECORD"] += original.splitlines(keepends=True)[0]
    write_wheel(wheel, files)
    assert checker.check_wheel(wheel, source)["failure"] == "invalid_record_member"
    rows = list(csv.reader(io.StringIO(original.decode())))
    rows[0][2] = "999"
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    files[f"{META}/RECORD"] = stream.getvalue().encode()
    write_wheel(wheel, files)
    assert checker.check_wheel(wheel, source)["failure"] == "record_size_mismatch"


@pytest.mark.parametrize("bad_name", ["../escape.py", "/absolute.py", "C:/drive.py", "a\\b.py", "pkg//a.py", "pkg/./a.py"])
def test_refuses_unsafe_archive_paths_without_extracting(sample, bad_name):
    source, wheel, files = sample
    files[bad_name] = b"never execute"
    write_wheel(wheel, files)
    assert checker.check_wheel(wheel, source)["failure"] == "unsafe_wheel_path"


def test_refuses_duplicate_and_symbolic_link_members(sample):
    source, wheel, files = sample
    write_wheel(wheel, files, duplicate="demo_mcp/__init__.py")
    assert checker.check_wheel(wheel, source)["failure"] == "duplicate_wheel_member"
    write_wheel(wheel, files, link="demo_mcp/__init__.py")
    assert checker.check_wheel(wheel, source)["failure"] == "linked_or_special_wheel_member"


@pytest.mark.parametrize("runtime_path", ["demo_mcp/_native.so", "demo_mcp/cached.pyc", "demo_mcp-0.1.0.data/purelib/new.py"])
def test_refuses_unsubstantiated_native_bytecode_and_relocated_layouts(sample, runtime_path):
    source, wheel, files = sample
    files[runtime_path] = b"unsupported runtime"
    files[f"{META}/RECORD"] = record_for({key: data for key, data in files.items() if not key.endswith("/RECORD")})
    write_wheel(wheel, files)
    report = checker.check_wheel(wheel, source)
    assert not report["ok"] and report["record_verified"]
    assert report["failure"].endswith("layout_unsupported")


def test_refuses_nonpure_wheel(sample):
    source, wheel, files = sample
    files[f"{META}/WHEEL"] = files[f"{META}/WHEEL"].replace(b"true", b"false")
    write_wheel(wheel, files)
    assert checker.check_wheel(wheel, source)["failure"] == "native_wheel_unsupported"


def test_limits_expanded_member_bytes_and_file_count(sample, monkeypatch):
    source, wheel, files = sample
    files["compressed.txt"] = b"a" * 1000
    write_wheel(wheel, files)
    monkeypatch.setattr(checker, "MAX_FILE_BYTES", 500)
    assert checker.check_wheel(wheel, source)["failure"] == "wheel_expanded_size_limit"
    monkeypatch.setattr(checker, "MAX_FILE_BYTES", 2000)
    monkeypatch.setattr(checker, "MAX_FILES", 3)
    assert checker.check_wheel(wheel, source)["failure"] == "wheel_member_limit"
    (source / "demo_mcp/extra.py").write_text("pass")
    (source / "demo_mcp/another.py").write_text("pass")
    assert checker.check_wheel(wheel, source)["failure"] == "source_inventory_limit"


def test_linked_source_is_not_followed(sample, tmp_path):
    source, wheel, _files = sample
    target = tmp_path / "outside.py"
    target.write_text("private")
    try:
        (source / "demo_mcp/linked.py").symlink_to(target)
    except OSError:
        pytest.skip("Windows symlink creation privilege unavailable")
    assert checker.check_wheel(wheel, source)["failure"] == "linked_source_refused"


def test_cli_returns_mismatch_and_preserves_existing_report(sample, tmp_path):
    source, wheel, _files = sample
    (source / "demo_mcp/__init__.py").write_bytes(b"# changed\n")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(wheel), "--source-root", str(source)],
        capture_output=True, text=True, timeout=15,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["failure"] == "python_source_mismatch"
    assert str(tmp_path) not in completed.stdout
    output = tmp_path / "report.json"
    output.write_text("preserve")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(wheel), "--source-root", str(source), "--output", str(output)],
        capture_output=True, text=True, timeout=15,
    )
    assert completed.returncode == 2
    assert output.read_text() == "preserve"
