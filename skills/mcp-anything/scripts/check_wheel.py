"""Statically compare a pure-Python wheel with its explicit source import root.

Example: python check_wheel.py app.whl --source-root ./src --output new-report.json
The source root maps directly to the wheel root (src/pkg/a.py -> pkg/a.py).
All runtime .py files must match byte for byte. Metadata and package data are
checked against RECORD, not compared with source; native/relocated Python and
bytecode-only layouts are unsupported. Nothing is installed, extracted or run.
Exit codes: 0 matching wheel, 1 failed/unsupported check, 2 invalid CLI/output.
"""
from __future__ import annotations

import argparse
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

MAX_FILES = 4096
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
NATIVE_SUFFIXES = {".so", ".pyd", ".dll", ".dylib"}


class CheckError(Exception):
    """A fixed, non-sensitive reason code safe for a shared report."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CheckError(code)


def _linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and not any(
        ord(char) < 32 or char in "\\:" for char in name
    ) and all(part not in {"", ".", ".."} for part in name.rstrip("/").split("/"))


def _source_hashes(root: Path) -> dict[str, str]:
    _require(root.is_dir() and not _linked(root), "invalid_source_root")
    hashes: dict[str, str] = {}
    total = 0
    examined = 0

    def failed(_error: OSError) -> None:
        raise CheckError("source_unreadable")

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        base = Path(directory)
        # The import root must identify packaged code, not a project/venv tree.
        examined += len(dirs) + len(files)
        _require(examined <= MAX_FILES, "source_inventory_limit")
        for name in dirs:
            _require(not _linked(base / name), "linked_source_refused")
        dirs[:] = [name for name in dirs if name != "__pycache__"]
        for name in sorted(files):
            path = base / name
            if path.suffix.lower() != ".py":
                continue
            _require(not _linked(path) and path.is_file(), "linked_source_refused")
            size = path.stat().st_size
            total += size
            _require(size <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES, "source_size_limit")
            # Bounded read also detects a file that grew after stat().
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            _require(len(data) == size, "source_changed_during_read")
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    _require(bool(hashes), "no_python_source")
    return hashes


def _wheel_files(wheel: Path) -> tuple[dict[str, bytes], str]:
    _require(wheel.is_file() and not _linked(wheel), "invalid_wheel_file")
    _require(wheel.stat().st_size <= MAX_TOTAL_BYTES, "wheel_size_limit")
    with zipfile.ZipFile(wheel) as archive:
        infos = archive.infolist()
        _require(len(infos) <= MAX_FILES, "wheel_member_limit")
        files: dict[str, bytes] = {}
        seen: set[str] = set()
        total = 0
        for info in infos:
            # ZipInfo normalizes backslashes on Windows and truncates NULs;
            # validate the original central-directory spelling as well.
            _require(_safe_name(info.orig_filename) and info.orig_filename == info.filename, "unsafe_wheel_path")
            key = info.filename.rstrip("/")
            _require(key not in seen, "duplicate_wheel_member")
            seen.add(key)
            mode = stat.S_IFMT(info.external_attr >> 16)
            _require(mode in {0, stat.S_IFREG, stat.S_IFDIR}, "linked_or_special_wheel_member")
            _require(not info.flag_bits & 1, "encrypted_wheel_unsupported")
            if info.is_dir():
                _require(info.file_size == 0, "invalid_wheel_directory")
                continue
            _require(mode != stat.S_IFDIR, "invalid_wheel_directory")
            total += info.file_size
            _require(info.file_size <= MAX_FILE_BYTES and total <= MAX_TOTAL_BYTES, "wheel_expanded_size_limit")
            with archive.open(info) as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            _require(len(data) == info.file_size, "wheel_member_size_mismatch")
            files[info.filename] = data
    dist_infos = {name.split("/", 1)[0] for name in files if name.split("/", 1)[0].endswith(".dist-info")}
    _require(len(dist_infos) == 1, "wheel_metadata_layout_unsupported")
    metadata = dist_infos.pop()
    _require(f"{metadata}/WHEEL" in files and f"{metadata}/RECORD" in files, "wheel_metadata_missing")
    header = BytesParser().parsebytes(files[f"{metadata}/WHEEL"])
    _require(header.get_all("Root-Is-Purelib") == ["true"], "native_wheel_unsupported")
    _require(header.get("Wheel-Version", "").split(".")[0] == "1", "wheel_version_unsupported")
    return files, metadata


def _verify_record(files: dict[str, bytes], metadata: str) -> None:
    record_name = f"{metadata}/RECORD"
    try:
        rows = list(csv.reader(io.StringIO(files[record_name].decode("utf-8"), newline=""), strict=True))
    except (UnicodeError, csv.Error):
        raise CheckError("invalid_record") from None
    _require(len(rows) <= MAX_FILES, "record_row_limit")
    seen: set[str] = set()
    for row in rows:
        _require(len(row) == 3, "invalid_record")
        name, encoded, size = row
        _require(_safe_name(name) and name in files and name not in seen, "invalid_record_member")
        seen.add(name)
        if name == record_name:
            _require(encoded == "" and size == "", "invalid_record_self_entry")
            continue
        _require(bool(re.fullmatch(r"[0-9]+", size)) and int(size) == len(files[name]), "record_size_mismatch")
        algorithm, separator, digest = encoded.partition("=")
        _require(separator == "=" and algorithm in {"sha256", "sha384", "sha512"}, "record_hash_unsupported")
        actual = base64.urlsafe_b64encode(hashlib.new(algorithm, files[name]).digest()).rstrip(b"=").decode("ascii")
        _require(digest == actual, "record_hash_mismatch")
    # PEP 427 signature envelopes are not themselves listed in RECORD. This
    # integrity check does not verify signatures or vendor authenticity.
    signatures = {f"{metadata}/RECORD.jws", f"{metadata}/RECORD.p7s"}
    _require(record_name in seen and set(files) - seen <= signatures, "record_members_missing")


def check_wheel(wheel: Path, source_root: Path) -> dict:
    """Return a bounded static report; never import the supplied source."""
    report = {
        "schema_version": 1, "ok": False, "record_verified": False,
        "source_python_count": 0, "wheel_python_count": 0,
        "differences": {"missing": [], "extra": [], "changed": []},
        "limitations": [
            "Source root must map directly to the wheel import root; all runtime .py files are compared byte for byte.",
            "Metadata and non-code package data are checked against RECORD, not compared to source.",
            "Native extensions, relocated Python and bytecode layouts are unsupported.",
            "Integrity and source equality do not prove tests ran, dependencies work, or vendor authenticity.",
        ],
    }
    try:
        source = _source_hashes(source_root)
        report["source_python_count"] = len(source)
        files, metadata = _wheel_files(wheel)
        _verify_record(files, metadata)
        report["record_verified"] = True
        code: dict[str, str] = {}
        for name, data in files.items():
            if name.startswith(metadata + "/"):
                continue
            suffix = PurePosixPath(name).suffix.lower()
            _require(suffix not in NATIVE_SUFFIXES | {".pyc", ".pyo"}, "native_or_bytecode_layout_unsupported")
            if suffix == ".py":
                _require(not name.split("/", 1)[0].endswith(".data"), "relocated_python_layout_unsupported")
                code[name] = hashlib.sha256(data).hexdigest()
        report["wheel_python_count"] = len(code)
        report["differences"] = {
            "missing": sorted(source.keys() - code.keys()),
            "extra": sorted(code.keys() - source.keys()),
            "changed": sorted(name for name in source.keys() & code.keys() if source[name] != code[name]),
        }
        report["ok"] = not any(report["differences"].values())
        if not report["ok"]:
            report["failure"] = "python_source_mismatch"
    except CheckError as error:
        report["failure"] = str(error)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        report["failure"] = "unreadable_or_invalid_input"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--source-root", type=Path, required=True, help="import root, such as src/; not its package subdirectory")
    parser.add_argument("--output", type=Path, help="new JSON report; existing files are preserved")
    args = parser.parse_args()
    try:
        if args.output and args.output.exists():
            raise ValueError("output exists")
        report = check_wheel(args.wheel, args.source_root)
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        else:
            print(serialized, end="")
    except (OSError, ValueError):
        print('{"ok": false, "failure": "invalid_output"}', file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
