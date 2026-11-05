"""Check release contents and boundaries using disposable source trees."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import zipfile

import pytest


def builder():
    path = Path(__file__).resolve().parents[1] / "build_release.py"
    spec = importlib.util.spec_from_file_location("build_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(root, relative, content="public source"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def skill_source(tmp_path):
    root = tmp_path / "source"
    put(root, "skills/mcp-anything/SKILL.md", "---\nname: mcp-anything\n---\n")
    put(root, "skills/mcp-anything/references/contract.md")
    put(root, "LICENSE", "original license")
    put(root, "THIRD_PARTY_NOTICES.md", "component notices")
    put(root, "docs/skill-install.md", "Install the mcp-anything folder.")
    put(root, "docs/skill-validation.md", "Skill-specific validation.")
    return root


def all_source(tmp_path):
    root = skill_source(tmp_path)
    put(root, "docs/validation.md", "Adapter-specific validation.")
    put(root, "scripts/accept_lammps.py")
    put(root, "scripts/accept_http.py")
    put(root, "adapters/lammps/pyproject.toml", 'version = "0.2.0"')
    wheel = root / "adapters/lammps/dist/lammps_mcp-0.2.0-py3-none-any.whl"
    wheel.parent.mkdir(parents=True)
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("lammps_mcp/__init__.py", '__version__ = "0.2.0"')
    return root


def test_skill_release_needs_no_adapter_or_wheel(tmp_path):
    root = skill_source(tmp_path)
    output = tmp_path / "release"
    result = builder().build_releases(root, output, "skill")
    filename = "mcp-anything-skill-0.4.1.zip"
    assert set(result) == {filename}
    assert not (root / "adapters").exists()
    archive_path = output / filename
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == result[filename]
    with zipfile.ZipFile(archive_path) as archive:
        assert "mcp-anything/SKILL.md" in archive.namelist()
        assert archive.read("INSTALL.md") == b"Install the mcp-anything folder."
        assert archive.read("VALIDATION.md") == b"Skill-specific validation."
        for line in archive.read("MANIFEST.sha256").decode().splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_full_release_has_independent_versions_and_excludes_runtime(tmp_path):
    root = all_source(tmp_path)
    for name in ("README.zh-CN.md", "CHANGELOG.md", "examples/cli/server.py"):
        put(root, name)
    private = (
        "INSPIRE.md", "docs/INSPIRE.md", "runtime/credentials.json",
        "scripts/__pycache__/cache.pyc", "adapters/lammps/jobs/private.json",
        "skills/mcp-anything/.venv/private.txt", "dist/old-release.zip",
    )
    for name in private:
        put(root, name, "PRIVATE_NOT_FOR_RELEASE")
    output = tmp_path / "release"
    result = builder().build_releases(root, output)
    assert set(result) == {
        "mcp-anything-0.4.1.zip", "mcp-anything-skill-0.4.1.zip", "lammps-mcp-0.2.0.zip",
    }
    with zipfile.ZipFile(output / "mcp-anything-0.4.1.zip") as archive:
        names = set(archive.namelist())
        assert {"README.zh-CN.md", "CHANGELOG.md", "examples/cli/server.py"} <= names
        assert "packages/lammps_mcp-0.2.0-py3-none-any.whl" in names
        assert not names.intersection(private)
        assert all(b"PRIVATE_NOT_FOR_RELEASE" not in archive.read(name) for name in names)
    with zipfile.ZipFile(output / "lammps-mcp-0.2.0.zip") as archive:
        assert archive.read("VALIDATION.md") == b"Adapter-specific validation."


def test_repeat_build_is_identical_and_does_not_bundle_its_output(tmp_path):
    root = all_source(tmp_path)
    output = root / "docs/generated-packages"
    release = builder()
    first = release.build_releases(root, output)
    second = release.build_releases(root, output)
    assert first == second
    with zipfile.ZipFile(output / "mcp-anything-0.4.1.zip") as archive:
        assert not any(name.startswith("docs/generated-packages/") for name in archive.namelist())


def test_source_inventory_refuses_environment_files(tmp_path):
    root = skill_source(tmp_path)
    put(root, "skills/mcp-anything/.env", "TOKEN=private")
    with pytest.raises(ValueError, match="environment file"):
        builder().build_releases(root, tmp_path / "release", "skill")
    assert not (tmp_path / "release").exists()


def test_source_inventory_refuses_linked_directory(tmp_path):
    root = skill_source(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("private")
    link = root / "skills/mcp-anything/linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symbolic links requires OS permission")
    with pytest.raises(ValueError, match="symlink or reparse point"):
        builder().build_releases(root, tmp_path / "release", "skill")


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions only")
def test_source_inventory_refuses_windows_junction(tmp_path):
    root = skill_source(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("private")
    junction = root / "skills/mcp-anything/linked"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
    )
    if result.returncode:
        pytest.skip("OS did not permit creating a test junction")
    try:
        with pytest.raises(ValueError, match="symlink or reparse point"):
            builder().build_releases(root, tmp_path / "release", "skill")
        assert (outside / "private.txt").read_text() == "private"
    finally:
        # rmdir removes this temporary junction itself, never its target tree.
        os.rmdir(junction)
