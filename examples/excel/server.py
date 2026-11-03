"""Small Windows Excel COM adapter for trusted, literal-data workbooks."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import threading
from typing import Annotated
import xml.etree.ElementTree as ET
import zipfile

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RESULT_BYTES = 64 * 1024
Cell = StrictStr | StrictInt | StrictFloat | StrictBool | None
Row = Annotated[list[Cell], Field(min_length=1, max_length=10)]
Matrix = Annotated[list[Row], Field(min_length=1, max_length=10)]
Name = Annotated[str, Field(min_length=1, max_length=90, strict=True)]
Sheet = Annotated[str, Field(min_length=1, max_length=31, strict=True)]
Address = Annotated[str, Field(min_length=2, max_length=20, strict=True)]


class WorkbookResult(BaseModel):
    file: str
    sheet: str
    excel_version: str
    bytes: int
    sha256: str
    owned_process_closed: bool


class CellsResult(BaseModel):
    file: str
    sheet: str
    address: str
    values: list[list[Cell]]
    excel_version: str
    truncated_cells: int
    owned_process_closed: bool


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Use a workspace and files without symlinks or Windows junctions")


def rectangle(address: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?", address)
    if not match:
        raise ValueError("Use one A1-style cell or rectangle, for example A1:C4")
    def column(value: str) -> int:
        number = 0
        for letter in value:
            number = number * 26 + ord(letter) - ord("A") + 1
        return number
    left, top = column(match[1]), int(match[2])
    right, bottom = column(match[3] or match[1]), int(match[4] or match[2])
    if not (1 <= left <= right <= 26 and 1 <= top <= bottom <= 1000):
        raise ValueError("This example limits addresses to A1:Z1000")
    if (right - left + 1) * (bottom - top + 1) > 100:
        raise ValueError("Select at most 100 cells")
    return top, left, bottom, right


def validate_values(values: list[list[Cell]], start_cell: str = "A1") -> tuple[int, int]:
    top, left, bottom, right = rectangle(start_cell)
    if top != bottom or left != right:
        raise ValueError("start_cell must be a single cell")
    if not values or len(values) > 10 or not values[0] or len(values[0]) > 10:
        raise ValueError("Use a rectangular matrix with 1–10 rows and columns")
    width = len(values[0])
    if top + len(values) - 1 > 1000 or left + width - 1 > 26:
        raise ValueError("Written cells must stay inside A1:Z1000")
    for row in values:
        if len(row) != width:
            raise ValueError("All rows must have the same length")
        for value in row:
            if value is not None and type(value) not in (str, int, float, bool):
                raise ValueError("Cells must contain text, finite numbers, booleans or null")
            if isinstance(value, str) and (len(value) > 256 or len(value.encode("utf-8")) > 512):
                raise ValueError("Cell text is limited to 256 characters and 512 UTF-8 bytes")
            if type(value) in (int, float) and (not math.isfinite(value) or abs(value) > 1e15):
                raise ValueError("Numbers must be finite with magnitude at most 1e15")
    return top, left


class Workspace:
    def __init__(self, root: Path):
        if ".." in root.parts:
            raise ValueError("Workspace must not contain parent traversal")
        root = root.absolute()
        reject_links(root)
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Workspace must be an existing directory")

    def file(self, name: str, suffix: str, *, output: bool = False) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,80}" + re.escape(suffix), name):
            raise ValueError(f"Use a plain workspace filename ending in {suffix}")
        if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("Reserved Windows filename")
        reject_links(self.root)
        path = self.root / name
        if path.exists() or path.is_symlink():
            reject_links(path)
            if output:
                raise FileExistsError("Output already exists; choose a new filename")
        elif not output:
            raise ValueError("Workbook does not exist in the selected workspace")
        if not output and (not path.is_file() or path.stat().st_size > MAX_FILE_BYTES):
            raise ValueError("Use a trusted workbook no larger than 5 MiB")
        return path

    def workbook(self, name: str) -> Path:
        path = self.file(name, ".xlsx")
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > 512 or sum(x.file_size for x in entries) > 16 * 1024 * 1024:
                    raise ValueError("Workbook contents exceed this example's limits")
                names = [x.filename.lower() for x in entries]
                if "xl/workbook.xml" not in names:
                    raise ValueError("Expected an ordinary .xlsx workbook")
                forbidden = ("xl/externallinks/", "xl/vbaproject", "xl/macrosheets/", "xl/dialogsheets/", "xl/embeddings/", "xl/activex/", "xl/querytables/", "xl/connections.xml")
                if any(name.startswith(forbidden) for name in names):
                    raise ValueError("This example accepts literal-data workbooks without macros, external links or connections")
                for item in entries:
                    if item.filename.lower().startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                        tree = ET.fromstring(archive.read(item))
                        if any(node.tag.rsplit("}", 1)[-1] == "f" for node in tree.iter()):
                            raise ValueError("Formula workbooks are outside this literal-data example")
        except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
            raise ValueError("Workbook is not a supported .xlsx file") from exc
        return path


class Excel:
    def __init__(self, workspace: Path, powershell: Path | None = None):
        self.workspace = Workspace(workspace)
        if os.name != "nt":
            raise ValueError("This example requires Windows and an installed Microsoft Excel")
        selected = str(powershell) if powershell else shutil.which("pwsh.exe")
        if not selected or not Path(selected).is_file():
            raise ValueError("PowerShell 7 is required; install it or supply --powershell with its absolute executable path")
        self.powershell = Path(selected).resolve(strict=True)
        self.worker = Path(__file__).with_name("worker.ps1")
        self.lock = threading.Lock()

    def _command(self, *args: str) -> list[str]:
        return [str(self.powershell), "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(self.worker), *args]

    def _run(self, operation: str, *, source: Path | None = None, destination: Path | None = None, **fields) -> dict:
        if not self.lock.acquire(blocking=False):
            raise ValueError("Excel is busy with another operation; retry after it finishes")
        try:
            with tempfile.TemporaryDirectory(prefix=".excel-mcp-", dir=self.workspace.root) as temporary:
                folder = Path(temporary)
                owner = folder / "owner.json"
                staged = folder / ("result" + destination.suffix) if destination else None
                request = {"operation": operation, "owner_file": str(owner), "source": str(source) if source else None, "output": str(staged) if staged else None, **fields}
                try:
                    process = subprocess.run(self._command(), input=json.dumps(request, ensure_ascii=True), capture_output=True, text=True, encoding="utf-8", timeout=45, check=False)
                except subprocess.TimeoutExpired:
                    cleanup = subprocess.run(self._command("-CleanupOwner", str(owner)), capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
                    if cleanup.returncode:
                        raise RuntimeError("Excel operation timed out and owned-process cleanup could not be confirmed") from None
                    raise ValueError("Excel operation timed out; its owned process was closed") from None
                try:
                    if len(process.stdout.encode("utf-8")) > MAX_RESULT_BYTES:
                        raise RuntimeError("Excel worker exceeded its output limit")
                    reply = json.loads(process.stdout.lstrip("\ufeff").strip())
                except (json.JSONDecodeError, RuntimeError):
                    cleanup = subprocess.run(self._command("-CleanupOwner", str(owner)), capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
                    if cleanup.returncode:
                        raise RuntimeError("Excel worker failed and owned-process cleanup could not be confirmed") from None
                    raise RuntimeError("Excel worker did not return a bounded valid result; its owned process was closed") from None
                if process.returncode or not reply.get("ok"):
                    raise ValueError(f"Excel operation failed ({reply.get('error', 'worker_error')}); check Excel installation and workbook")
                if not reply.get("owned_process_closed"):
                    raise RuntimeError("Excel result refused because owned-process cleanup was not confirmed")
                result = reply["result"]
                result["owned_process_closed"] = True
                if staged is not None:
                    if not staged.is_file() or not 0 < staged.stat().st_size <= MAX_FILE_BYTES:
                        raise ValueError("Excel output is missing or larger than 5 MiB")
                    reject_links(self.workspace.root)
                    # Both paths are on the workspace volume. link() publishes the
                    # completed file atomically and refuses an existing destination.
                    os.link(staged, destination)
                    result.update(file=destination.name, bytes=destination.stat().st_size, sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
                else:
                    result["file"] = source.name
                return result
        finally:
            self.lock.release()

    def create(self, output: str, values: list[list[Cell]]) -> WorkbookResult:
        validate_values(values)
        destination = self.workspace.file(output, ".xlsx", output=True)
        return WorkbookResult(**self._run("create", destination=destination, values=values, sheet="Data", row=1, column=1))

    def read(self, workbook: str, sheet: str, address: str) -> CellsResult:
        rectangle(address)
        if not sheet or len(sheet) > 31:
            raise ValueError("Choose a worksheet name of 1–31 characters")
        return CellsResult(**self._run("read", source=self.workspace.workbook(workbook), sheet=sheet, address=address))

    def write_copy(self, workbook: str, output: str, sheet: str, start_cell: str, values: list[list[Cell]]) -> WorkbookResult:
        row, column = validate_values(values, start_cell)
        destination = self.workspace.file(output, ".xlsx", output=True)
        return WorkbookResult(**self._run("write_copy", source=self.workspace.workbook(workbook), destination=destination, sheet=sheet, row=row, column=column, values=values))

def create_server(excel: Excel) -> FastMCP:
    server = FastMCP("excel-literal-workbooks")

    @server.tool()
    def create_workbook(output: Name, values: Matrix) -> WorkbookResult:
        """Create a new .xlsx with literal values in Data!A1; never overwrite a file."""
        return excel.create(output, values)

    @server.tool()
    def read_cells(workbook: Name, address: Address, sheet: Sheet = "Data") -> CellsResult:
        """Read up to 100 cells from a trusted literal-data workbook; text may be clipped."""
        return excel.read(workbook, sheet, address)

    @server.tool()
    def write_cells_copy(workbook: Name, output: Name, start_cell: Address, values: Matrix, sheet: Sheet = "Data") -> WorkbookResult:
        """Write literal cells into a NEW workbook copy; leave the source file unchanged."""
        return excel.write_copy(workbook, output, sheet, start_cell, values)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--powershell", type=Path, help="Operator-selected PowerShell 7 executable; defaults to pwsh.exe on PATH")
    args = parser.parse_args()
    try:
        excel = Excel(args.workspace, args.powershell)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    create_server(excel).run(transport="stdio")


if __name__ == "__main__":
    main()
