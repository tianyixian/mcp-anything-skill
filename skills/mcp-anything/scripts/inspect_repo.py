"""Bounded static repository inventory; never executes repository code."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.parse import urlsplit

EXCLUDE = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".ssh", ".aws"}
MANIFESTS = {"pyproject.toml", "setup.py", "setup.cfg", "package.json", "Cargo.toml", "go.mod", "CMakeLists.txt", "Makefile", "requirements.txt"}


def is_reparse_point(path: Path) -> bool:
    attributes = path.lstat()
    return stat.S_ISLNK(attributes.st_mode) or bool(
        getattr(attributes, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def sensitive(name: str) -> bool:
    low = name.lower()
    return low.startswith(".env") or any(x in low for x in ("credential", "secret", "token", "id_rsa", "id_ed25519")) or low.endswith((".pem", ".key", ".p12"))


def git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(root), *args], capture_output=True, text=True, timeout=10, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def inspect_repo(root: Path, source_url: str | None = None, max_files: int = 5000) -> dict:
    # Check the path supplied by the caller before resolve can hide a link.
    if ".." in root.parts:
        raise ValueError("repository path must not contain parent traversal")
    root = root.absolute()
    for component in reversed((root, *root.parents)):
        if is_reparse_point(component):
            raise ValueError("repository path must not pass through a symlink or reparse point; use its actual path")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository must be a directory")
    if not 1 <= max_files <= 100000:
        raise ValueError("max-files must be between 1 and 100000")
    if source_url:
        parts = urlsplit(source_url)
        if parts.scheme != "https" or parts.hostname != "github.com" or parts.username or parts.password or parts.query or parts.fragment or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", parts.path):
            raise ValueError("source-url must be a public GitHub HTTPS repository URL without credentials or query")
    manifests, licenses, docs, examples, code = [], [], [], [], []
    count = 0
    truncated = False
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE and not sensitive(d) and not is_reparse_point(Path(directory) / d))
        for name in sorted(names):
            path = Path(directory) / name
            if sensitive(name) or is_reparse_point(path) or not path.is_file():
                continue
            count += 1
            if count > max_files:
                truncated = True
                break
            relative = path.relative_to(root).as_posix()
            lower = name.lower()
            if name in MANIFESTS:
                manifests.append(relative)
            if lower.startswith(("license", "copying", "notice")):
                licenses.append(relative)
            if lower.startswith("readme") or (relative.startswith("doc") and lower.endswith((".md", ".rst"))):
                if len(docs) < 50:
                    docs.append(relative)
            if any(x in {"example", "examples", "demo", "demos"} for x in path.relative_to(root).parts) and len(examples) < 40:
                examples.append(relative)
            if lower in {"__main__.py", "cli.py", "main.py", "main.cpp", "main.c", "main.rs", "server.py"} and len(code) < 40:
                code.append(relative)
        if truncated:
            break
    commit = git_value(root, "rev-parse", "--verify", "HEAD")
    git_root = git_value(root, "rev-parse", "--show-toplevel")
    if git_root is None or Path(git_root).resolve() != root:
        commit = None  # Do not accidentally attribute an enclosing repository.
    return {
        "schema_version": 1,
        "source_url": source_url,
        "commit": commit,
        "sparse_checkout": git_value(root, "config", "--bool", "core.sparseCheckout") == "true" if commit else False,
        "files_considered": min(count, max_files),
        "truncated": truncated,
        "build_manifests": manifests,
        "license_files": licenses,
        "documentation_candidates": docs,
        "example_candidates": examples,
        "entrypoint_candidates": code,
        "limitations": ["Static path inventory only; no source code executed or file contents exported.", "Candidates are not a verified API or a license determination.", "Symlinks/reparse points, credential-like names and generated/dependency directories are excluded."],
        "next_steps": ["Read the license and documented public interface.", "Specify the requested capability and trust boundary.", "Implement and test a real operation through MCP."],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--source-url")
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_repo(args.repository, args.source_url, args.max_files)
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            if args.output.exists():
                raise FileExistsError("output already exists; choose a new inspection file")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
            print("Repository inventory saved; no source code was executed.")
        else:
            print(serialized, end="")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Cannot inspect repository: {exc}\n")


if __name__ == "__main__":
    main()
