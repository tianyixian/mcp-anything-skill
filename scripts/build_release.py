"""Build reproducible source archives from explicitly selected project files."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat
import zipfile

VERSION = "0.4.3"
ADAPTER_VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    "__pycache__", ".pytest_cache", ".ruff_cache", ".git", ".venv",
    "dist", "build", "jobs", "workspace", "node_modules",
}
EXCLUDED_FILES = {"INSPIRE.md"}
ROOT_FILES = {
    "README.md", "README.zh-CN.md", "CHANGELOG.md", "LICENSE", ".gitignore", ".gitattributes",
    "SECURITY.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md",
    "requirements-dev.in", "requirements-dev.lock", "requirements-engine.txt", "pytest.ini",
}
ROOT_DIRS = {"skills", "adapters", "docs", "scripts", ".github", "examples"}
SKILL_FILES = {
    "LICENSE", "THIRD_PARTY_NOTICES.md", "docs/skill-install.md", "docs/skill-validation.md",
}


def is_reparse_point(path: Path) -> bool:
    """Reject symlinks and Windows junctions, including on Python 3.11."""
    attributes = path.lstat()
    return stat.S_ISLNK(attributes.st_mode) or bool(
        getattr(attributes, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def check_source_path(root: Path, path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if is_reparse_point(candidate):
            raise ValueError(f"Refusing release symlink or reparse point: {candidate.relative_to(root)}")


def source_files(root: Path = ROOT, *, skill_only: bool = False, output: Path | None = None) -> list[Path]:
    """Inventory only distributable trees; never traverse links or runtime folders."""
    selected: set[Path] = set()
    directories = {"skills/mcp-anything"} if skill_only else ROOT_DIRS
    single_files = SKILL_FILES if skill_only else ROOT_FILES

    def include_file(path: Path) -> None:
        if path.name in EXCLUDED_FILES or path.suffix in {".pyc", ".pyo", ".log"}:
            return
        check_source_path(root, path)
        if path.name == ".env" or path.name.startswith(".env."):
            raise ValueError(f"Refusing environment file: {path.relative_to(root)}")
        if path.is_file():
            selected.add(path)

    for relative in sorted(single_files):
        path = root / relative
        if path.exists() or path.is_symlink():
            include_file(path)
    for relative in sorted(directories):
        tree = root / relative
        if not tree.exists() and not tree.is_symlink():
            continue
        check_source_path(root, tree)
        for directory, dirs, names in os.walk(tree, topdown=True, followlinks=False):
            base = Path(directory)
            retained = []
            for name in sorted(dirs):
                candidate = base / name
                if name in EXCLUDED_PARTS or name.endswith(".egg-info") or candidate == output:
                    continue
                check_source_path(root, candidate)
                retained.append(name)
            dirs[:] = retained
            for name in sorted(names):
                include_file(base / name)
    return sorted(selected)


def write_archive(path: Path, entries: dict[str, bytes]) -> str:
    entries = dict(entries)
    manifest = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(entries.items()))
    entries["MANIFEST.sha256"] = manifest.encode()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 31, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"Corrupt archive: {path}")
        for line in archive.read("MANIFEST.sha256").decode().splitlines():
            digest, name = line.split("  ", 1)
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise RuntimeError(f"Manifest mismatch: {name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_releases(root: Path, output: Path, target: str = "all") -> dict[str, str]:
    if target not in {"skill", "all"}:
        raise ValueError("target must be skill or all")
    root = root.resolve()
    output = output.resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError("output must not be the source root or its parent")
    files = source_files(root, skill_only=target == "skill", output=output)
    complete = {p.relative_to(root).as_posix(): p.read_bytes() for p in files}
    required = SKILL_FILES | {"skills/mcp-anything/SKILL.md"}
    missing = required - complete.keys()
    if missing:
        raise ValueError("Missing required skill release files: " + ", ".join(sorted(missing)))
    skill = {
        name.removeprefix("skills/"): data
        for name, data in complete.items() if name.startswith("skills/mcp-anything/")
    }
    skill.update({
        "LICENSE": complete["LICENSE"],
        "THIRD_PARTY_NOTICES.md": complete["THIRD_PARTY_NOTICES.md"],
        "INSTALL.md": complete["docs/skill-install.md"],
        "VALIDATION.md": complete["docs/skill-validation.md"],
    })
    releases = {f"mcp-anything-skill-{VERSION}.zip": skill}
    if target == "all":
        adapter_required = {"docs/validation.md", "scripts/accept_lammps.py", "scripts/accept_http.py"}
        missing = adapter_required - complete.keys()
        if missing:
            raise ValueError("Missing required adapter release files: " + ", ".join(sorted(missing)))
        adapter = {
            name.removeprefix("adapters/lammps/"): data
            for name, data in complete.items() if name.startswith("adapters/lammps/")
        }
        wheel = root / "adapters/lammps/dist" / f"lammps_mcp-{ADAPTER_VERSION}-py3-none-any.whl"
        if not wheel.is_file():
            raise ValueError("Build the adapter wheel first: python -m build adapters/lammps (or use --target skill)")
        check_source_path(root, wheel)
        complete[f"packages/{wheel.name}"] = wheel.read_bytes()
        adapter[f"packages/{wheel.name}"] = complete[f"packages/{wheel.name}"]
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "scripts/accept_lammps.py", "scripts/accept_http.py"):
            adapter[name] = complete[name]
        adapter["VALIDATION.md"] = complete["docs/validation.md"]
        releases = {
            f"mcp-anything-{VERSION}.zip": complete,
            **releases,
            f"lammps-mcp-{ADAPTER_VERSION}.zip": adapter,
        }
    output.mkdir(parents=True, exist_ok=True)
    hashes = {name: write_archive(output / name, entries) for name, entries in releases.items()}
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="utf-8",
    )
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--target", choices=("skill", "all"), default="all",
                        help="skill builds independently; all additionally packages the existing LAMMPS wheel")
    args = parser.parse_args()
    try:
        hashes = build_releases(ROOT, args.output, args.target)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    for filename, digest in hashes.items():
        print(f"{filename}: sha256 {digest}")


if __name__ == "__main__":
    main()
