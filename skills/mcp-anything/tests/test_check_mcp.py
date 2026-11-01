"""Real stdio acceptance checks, including results and sanitized failures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_mcp.py"
spec = importlib.util.spec_from_file_location("check_mcp", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def server(tmp_path):
    target = tmp_path / "server.py"
    target.write_text('''import os
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("acceptance-fixture")
@mcp.tool()
def add(a: int, b: int) -> dict[str, object]:
    return {"sum": a + b, "details": {"kind": "integer", "extra": True}}
@mcp.tool()
def fail() -> dict[str, object]:
    raise ValueError("SENSITIVE_SERVER_ERROR_DO_NOT_COPY")
@mcp.tool()
def configured() -> dict[str, object]:
    return {"configured": os.environ.get("MCP_CHECK_TEST_VALUE") == "runtime-only"}
mcp.run()
''', encoding="utf-8")
    return {"command": sys.executable, "args": [str(target)], "timeout_seconds": 20}


@pytest.mark.asyncio
async def test_real_calls_expectations_error_and_environment(server, monkeypatch):
    monkeypatch.setenv("MCP_CHECK_TEST_VALUE", "runtime-only")
    plan = {**server, "required_tools": ["add", "fail"], "cases": [
        {"tool": "add", "arguments": {"a": 2, "b": 3}, "expect": {"sum": 5, "details": {"kind": "integer"}}},
        {"tool": "add", "arguments": {"a": 2, "b": 3}, "expect": {"sum": 5, "details": {"kind": "integer", "extra": True}}, "match": "exact"},
        {"tool": "fail", "expect_error": True},
        {"tool": "configured", "expect": {"configured": True}},
    ]}
    report = await checker.check(plan)
    assert report["ok"]
    assert report["validation_level"] == "declared_calls_checked"
    assert report["tool_count"] == 3
    serialized = json.dumps(report)
    for private in [server["args"][0], "runtime-only", "MCP_CHECK_TEST_VALUE", "SENSITIVE_SERVER_ERROR", '"sum"']:
        assert private not in serialized


@pytest.mark.asyncio
async def test_real_mismatch_is_failure_and_exact_rejects_extra_keys(server):
    report = await checker.check({**server, "cases": [
        {"tool": "add", "arguments": {"a": 2, "b": 3}, "expect": {"sum": 6}},
        {"tool": "add", "arguments": {"a": 2, "b": 3}, "expect": {"sum": 5}, "match": "exact"},
    ]})
    assert not report["ok"]
    assert [case["failure"] for case in report["cases"]] == ["structured_result_mismatch"] * 2


@pytest.mark.asyncio
async def test_discovery_only_and_missing_required_tool(server):
    report = await checker.check(server)
    assert report["ok"] and report["protocol_connected"]
    assert report["validation_level"] == "protocol_only"
    missing = await checker.check({**server, "required_tools": ["not_implemented"]})
    assert not missing["ok"]
    assert missing["failure"] == "required_tool_missing"


@pytest.mark.asyncio
async def test_timeout_and_process_failure_do_not_export_details(tmp_path):
    target = tmp_path / "wait.py"
    target.write_text("import time; time.sleep(20)", encoding="utf-8")
    report = await checker.check({"command": sys.executable, "args": [str(target)], "timeout_seconds": 1})
    assert not report["ok"] and report["failure"] == "timeout"
    missing = await checker.check({"command": str(tmp_path / "private-missing-program")})
    assert not missing["ok"] and missing["failure"] == "protocol_or_process_error"
    assert str(tmp_path) not in json.dumps([report, missing])


@pytest.mark.parametrize("changes", [
    {"command": "https://example.com/mcp"},
    {"env": {"SECRET": "hidden"}},
    {"timeout_seconds": 0},
    {"timeout_seconds": True},
    {"args": "--shell bad"},
    {"cases": [{"tool": "add", "expect": {}}]},
    {"cases": [{"tool": "add", "arguments": {"api_key": "hidden"}, "expect": {"ok": True}}]},
    {"cases": [{"tool": "fail", "expect_error": True, "expect": {"ok": False}}]},
])
def test_rejects_invalid_or_credential_bearing_plans(changes):
    with pytest.raises(ValueError):
        checker.validate_plan({"command": "python", **changes})


def test_matching_distinguishes_boolean_and_number():
    assert not checker.matches({"ok": 1}, {"ok": True})
    assert checker.matches({"items": [{"value": 1, "extra": 2}]}, {"items": [{"value": 1}]})
    assert not checker.matches({"items": [1, 2]}, {"items": [1]})


def test_cli_failure_exit_code_and_existing_report_preserved(server, tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({**server, "cases": [{"tool": "add", "arguments": {"a": 1, "b": 1}, "expect": {"sum": 9}}]}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(plan)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert json.loads(result.stdout)["cases"][0]["failure"] == "structured_result_mismatch"
    assert "SENSITIVE" not in result.stderr
    output = tmp_path / "existing.json"
    output.write_text("preserve")
    result = subprocess.run([sys.executable, str(SCRIPT), str(plan), "--output", str(output)], capture_output=True, timeout=30)
    assert result.returncode == 2
    assert output.read_text() == "preserve"


def test_cli_cleanup_timeout_cannot_report_success(tmp_path):
    server = tmp_path / "slow_cleanup.py"
    # A minimal actual stdio peer starts without SDK import overhead, so the
    # short deadline reliably expires during shutdown on Windows and POSIX.
    server.write_text('''import json, sys, time
for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    if request["method"] == "initialize":
        result = {"protocolVersion": request["params"]["protocolVersion"],
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "slow-cleanup", "version": "1"}}
    else:
        result = {"tools": []}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
# Complete protocol discovery promptly, then delay process shutdown.
time.sleep(6)
''', encoding="utf-8")
    plan = tmp_path / "cleanup-plan.json"
    plan.write_text(json.dumps({
        "command": sys.executable, "args": [str(server)], "timeout_seconds": 1,
    }), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(plan)], capture_output=True, text=True, timeout=25,
    )
    report = json.loads(result.stdout)
    assert report["protocol_connected"] is True
    assert report["failure"] == "timeout"
    assert report["ok"] is False
    assert result.returncode == 1
