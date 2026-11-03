"""Locate software and suggest interfaces without launching it or fetching URLs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
from urllib.parse import urlsplit, urlunsplit

SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", "cache", "logs"}
MANIFESTS = {"pyproject.toml", "package.json", "cargo.toml", "go.mod", "cmakelists.txt"}


def linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def private_name(name: str) -> bool:
    name = name.casefold()
    return name.startswith(".env") or any(word in name for word in ("secret", "credential", "token")) or name.endswith((".pem", ".key", ".p12"))


def registered_windows_apps(name: str) -> list[dict]:
    """Check a bounded App Paths registry, not all installed software/user files."""
    if os.name != "nt":
        return []
    import winreg

    words = set(re.findall(r"[a-z0-9]+", name.casefold())) - {"microsoft", "application", "exe"}
    if not words:
        return []
    found: dict[str, dict] = {}
    subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as key:
                    for index in range(min(winreg.QueryInfoKey(key)[0], 512)):
                        entry = winreg.EnumKey(key, index)
                        stem = Path(entry).stem.casefold()
                        if stem not in words:
                            continue
                        try:
                            with winreg.OpenKey(key, entry) as item:
                                value, _ = winreg.QueryValueEx(item, "")
                            if not isinstance(value, str):
                                continue
                            path = Path(os.path.expandvars(value.strip('"')))
                            if path.is_absolute() and path.is_file():
                                resolved = str(path.resolve())
                                found[resolved.casefold()] = {"path": resolved, "evidence": "Windows App Paths registration"}
                        except OSError:
                            continue
            except OSError:
                continue
    return list(found.values())[:16]


def inventory(root: Path, max_entries: int, max_depth: int) -> dict:
    """Bound directory enumeration itself; do not read file bodies or follow links."""
    stack = [(root, 0)]
    items: list[dict] = []
    examined = 0
    omitted_links = 0
    partial = False
    issues: list[str] = []
    while stack and examined < max_entries:
        directory, depth = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if examined >= max_entries:
                        partial = True
                        break
                    examined += 1
                    path = Path(entry.path)
                    try:
                        if linked(path):
                            omitted_links += 1
                            continue
                        low = entry.name.casefold()
                        if private_name(low) or low in SKIP:
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if depth < max_depth:
                                stack.append((path, depth + 1))
                            else:
                                partial = True
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        kind = None
                        if low in MANIFESTS:
                            kind = "build_manifest"
                        elif low.endswith(".asar"):
                            kind = "electron_archive_candidate"
                        elif low.endswith((".bat", ".cmd", ".ps1", ".sh")):
                            kind = "script_launcher_candidate"
                        elif low.endswith((".exe", ".com")) or (os.name != "nt" and entry.stat().st_mode & 0o111):
                            kind = "executable_candidate"
                        elif low.startswith(("readme", "license", "copying")):
                            kind = "documentation"
                        elif low.endswith((".tlb", ".olb")):
                            kind = "automation_type_library_candidate"
                        if kind:
                            if len(items) < 100:
                                items.append({"path": path.relative_to(root).as_posix(), "kind": kind})
                            else:
                                partial = True
                    except OSError:
                        partial = True
                        if "Some entries could not be inspected." not in issues:
                            issues.append("Some entries could not be inspected.")
        except OSError:
            partial = True
            if "Some directories could not be listed." not in issues:
                issues.append("Some directories could not be listed.")
    return {"entries_examined": examined, "partial": partial or bool(stack),
            "links_omitted": omitted_links, "candidates": sorted(items, key=lambda x: x["path"]), "issues": issues}


def discover(target: str, kind: str = "auto", task: str | None = None,
             max_entries: int = 2000, max_depth: int = 4) -> dict:
    if kind not in {"auto", "command", "path", "url"}:
        raise ValueError("unknown target kind")
    if not target or len(target) > 4096 or any(ord(c) < 32 for c in target):
        raise ValueError("target must be a nonempty name, path or URL without control characters")
    if not 1 <= max_entries <= 20000 or not 0 <= max_depth <= 8:
        raise ValueError("max-entries must be 1..20000 and max-depth 0..8")
    if task is not None and (len(task) > 2000 or any(ord(c) < 32 for c in task)):
        raise ValueError("task must be one line of at most 2000 characters")
    result = {"schema_version": 1, "status": "needs_location", "source_kind": None,
              "target": target, "requested_task": task, "locations": [], "inventory": None,
              "interface_candidates": [], "verified_operations": [], "target_executed": False,
              "network_accessed": False,
              "limitations": ["Discovery only: no interface or business operation has been tested.",
                              "Local reports may contain installation paths; review before publishing.",
                              "Directory scans exclude child links, credential-like names and dependency/cache directories; no file bodies are read."]}
    if kind == "url" or (kind == "auto" and "://" in target):
        parts = urlsplit(target)
        try:
            _ = parts.port
        except ValueError as exc:
            raise ValueError("invalid URL port") from exc
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("use an HTTP(S) URL without credentials, query or fragment")
        if any(c.isspace() for c in target) or "\\" in target:
            raise ValueError("invalid URL characters")
        result["target"] = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        repo = parts.hostname.casefold() == "github.com" and re.fullmatch(r"/[\w.-]+/[\w.-]+/?", parts.path)
        result.update(status="candidate", source_kind="repository_url" if repo else "web_url")
        routes = ["existing_mcp", "documented_api", "repository_interface"] if repo else ["existing_mcp", "documented_api", "browser_automation"]
    else:
        path = Path(target).expanduser()
        looks_path = kind == "path" or path.is_absolute() or any(c in target for c in ("/", "\\"))
        if kind != "command" and (looks_path or path.exists()):
            if not path.exists():
                raise ValueError("target path does not exist")
            path = path.resolve(strict=True)
            if not path.is_file() and not path.is_dir():
                raise ValueError("target must be a regular file or directory")
            result["locations"] = [{"path": str(path), "evidence": "caller-selected path"}]
        else:
            executable = shutil.which(target)
            if executable:
                result["locations"] = [{"path": str(Path(executable).resolve()), "evidence": "PATH lookup; not executed"}]
            else:
                result["locations"] = registered_windows_apps(target)
            path = Path(result["locations"][0]["path"]) if len(result["locations"]) == 1 else None
        if path is not None and result["locations"]:
            result["status"] = "candidate"
            result["source_kind"] = "installation_directory" if path.is_dir() else "local_file"
            if path.is_dir():
                result["inventory"] = inventory(path, max_entries, max_depth)
            routes = ["existing_mcp", "documented_cli", "library_or_automation_api", "desktop_automation", "rea_inspection"]
        else:
            result["source_kind"] = "software_name"
            result["status"] = "needs_selection" if result["locations"] else "needs_location"
            routes = ["existing_mcp", "locate_installation"]
            result["limitations"].append("Name lookup covers PATH and bounded Windows App Paths only; missing results do not prove the software is absent.")
    result["interface_candidates"] = [{"route": route, "verified": False} for route in routes]
    result["next_steps"] = ["Confirm the target, installed version and desired operation.",
                            "Inspect documented interfaces before GUI automation or optional REA analysis.",
                            "Implement the selected operation, then verify it against the real software through MCP."]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("--kind", choices=("auto", "command", "path", "url"), default="auto")
    parser.add_argument("--task")
    parser.add_argument("--max-entries", type=int, default=2000)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = discover(args.target, args.kind, args.task, args.max_entries, args.max_depth)
        serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
            print("Software discovery saved; target was not launched and no URL was fetched.")
        else:
            print(serialized, end="")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Cannot discover target: {exc}\n")


if __name__ == "__main__":
    main()
