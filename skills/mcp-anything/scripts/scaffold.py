"""Generate a minimal, honest Python stdio MCP adapter project."""
from __future__ import annotations

import argparse
import keyword
from pathlib import Path
import re
import shutil
import stat
import tempfile


def is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat()
    except FileNotFoundError:
        return False  # A scaffold destination normally does not exist yet.
    return stat.S_ISLNK(attributes.st_mode) or bool(
        getattr(attributes, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def scaffold(name: str, module: str, output: Path) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("name must be a lowercase package name, at most 64 characters")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", module) or keyword.iskeyword(module) or len(module) > 64:
        raise ValueError("module must be a valid lowercase Python identifier")
    if ".." in output.parts:
        raise ValueError("output must not contain parent traversal")
    output = output.absolute()
    for parent in reversed((output, *output.parents)):
        if is_reparse_point(parent):
            raise ValueError("output must not pass through a symlink or reparse point")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("output already exists and is not an empty directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    files = {
        "pyproject.toml": f'''[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "0.1.0"
description = "MCP adapter scaffold; implement the upstream capability before use"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["mcp>=1.26,<2"]

[project.scripts]
{name} = "{module}.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/{module}"]
''',
        f"src/{module}/__init__.py": '__version__ = "0.1.0"\n',
        f"src/{module}/__main__.py": "from .server import main\n\nmain()\n",
        f"src/{module}/server.py": f'''"""Generated MCP transport. Implement the software capability before release."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{name}")


@mcp.tool()
def adapter_info() -> dict[str, object]:
    """Report scaffold readiness; this does not execute upstream software."""
    return {{"name": "{name}", "adapter_ready": False,
            "reason": "Only the transport scaffold is implemented."}}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
''',
        "README.md": f'''# {name}

Generated using the MCP Anything skill. **This is an unfinished scaffold.**

Install with `python -m pip install -e .` and start with `{name}`.
Only `adapter_info` exists and reports `adapter_ready: false`.

Before release: implement the selected upstream operation, record its source
and license, add real protocol/engine tests, and replace this README with
installation, input/output, trust and failure behavior instructions.
''',
        ".gitignore": "__pycache__/\n*.egg-info/\n.venv/\n.pytest_cache/\nbuild/\ndist/\n.env\n",
        "tests/.gitkeep": "",
    }
    staging = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=output.parent))
    try:
        for relative, content in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        if output.exists():
            output.rmdir()  # Only the verified empty directory; never recursive.
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        scaffold(args.name, args.module, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Cannot generate project: {exc}\n")
    print(f"Created {args.name}. Transport scaffold only; upstream capability is not implemented.")


if __name__ == "__main__":
    main()
