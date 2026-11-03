"""Workbook boundaries plus actual Excel acceptance when the engine is installed."""
import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter = load("excel_example_server", "server.py")
acceptance = load("excel_example_verify", "verify.py")


def test_workspace_preserves_existing_outputs_and_rejects_paths(tmp_path):
    workspace = adapter.Workspace(tmp_path)
    existing = tmp_path / "source.xlsx"
    existing.write_bytes(b"preserve me")
    with pytest.raises(FileExistsError):
        workspace.file("source.xlsx", ".xlsx", output=True)
    for name in ("../outside.xlsx", "C:\\data.xlsx", "nested/file.xlsx", "CON.xlsx", "file.xlsx:stream"):
        with pytest.raises(ValueError):
            workspace.file(name, ".xlsx", output=True)
    assert existing.read_bytes() == b"preserve me"


@pytest.mark.parametrize("member,content", [
    ("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c><f>WEBSERVICE("https://example.invalid")</f></c></row></sheetData></worksheet>'),
    ("xl/externalLinks/externalLink1.xml", "<externalLink/>"),
    ("xl/connections.xml", "<connections/>"),
    ("xl/vbaProject.bin", "not a macro"),
    ("xl/macrosheets/sheet1.xml", "<worksheet/>"),
])
def test_formula_and_active_content_refused_before_excel(tmp_path, member, content):
    path = tmp_path / "active.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", "<workbook/>")
        archive.writestr(member, content)
    with pytest.raises(ValueError, match="Formula|literal-data"):
        adapter.Workspace(tmp_path).workbook(path.name)


def test_bounds_apply_to_cells_and_values():
    for address in ("A1:Z1000", "A0", "XFD1", "A1,B1", "B2:A1"):
        with pytest.raises(ValueError):
            adapter.rectangle(address)
    for values in ([[1], [2, 3]], [[float("inf")]], [[1e100]], [["界" * 256]]):
        with pytest.raises(ValueError):
            adapter.validate_values(values)
    # Formula-looking strings are admitted as literals; the actual Excel check
    # proves they are written as text and remain text after save/reopen.
    assert adapter.validate_values([["=1+1", True, None]]) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.skipif(not acceptance.available(), reason="Requires Windows, PowerShell 7 and installed Microsoft Excel")
async def test_real_excel_mcp_workflow(tmp_path):
    report = await acceptance.verify(tmp_path)
    assert report["source_hash_unchanged"]
    assert report["formula_like_input_stored_as_literal"]
    assert report["owned_process_cleanup_confirmed_each_call"]
