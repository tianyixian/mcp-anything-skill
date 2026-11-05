"""Check a trusted local stdio MCP server using explicit JSON test cases.

Plan example (paths are relative to the caller's working directory):
{"command": "python", "args": ["server.py"], "required_tools": ["add"],
 "cases": [{"tool": "add", "arguments": {"a": 2, "b": 3},
            "expect": {"sum": 5}, "match": "subset"}], "timeout_seconds": 30}

Each success case requires an expected structured result. Use match="exact"
for full equality or expect_error=true for a negative case. An empty cases
list checks only the protocol; it cannot establish backend correctness.
The server inherits the current process environment. Run only a trusted local
command; set credentials in that environment, never in the plan. Commands,
arguments, environment, server output, and result values are omitted from the
report. Exit codes: 0 checks passed, 1 check failed, 2 invalid plan/output.
timeout_seconds is a session budget, not a hard process wall-clock limit:
SDK transport cleanup and process termination can take additional time.
Client compatibility has been exercised with MCP Python SDK 1.30.0 and 2.3.0.
Use a separate environment for each incompatible dependency set; the checker
does not upgrade the SDK or the server. SDK-version/protocol metadata is safe
to retain; sdk_incompatible identifies a client prerequisite problem before
it can be mistaken for a failed backend operation.
"""
from __future__ import annotations

import argparse
import asyncio
from importlib import metadata
import inspect
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
CREDENTIAL_KEYS = {
    "env", "authorization", "password", "secret", "token", "access_token",
    "refresh_token", "api_key", "apikey", "client_secret", "headers",
}
SDK_HINT = (
    "Run this checker in an isolated environment with MCP Python SDK 1.30.0 "
    "or 2.3.0, or adapt and test the client API for the installed SDK. "
    "Keep the server executable in its own dependency environment."
)


class SdkIncompatible(Exception):
    """A client API requirement is missing; its reason is a fixed safe code."""

    def __init__(self, issue: str, version: str | None = None):
        super().__init__(issue)
        self.version = version


def _model_field(model: Any, *names: str) -> str:
    fields = getattr(model, "model_fields", {})
    for name in names:
        if name in fields:
            return name
    raise SdkIncompatible("required_model_field_missing")


def _load_sdk() -> dict:
    """Resolve versioned client API names before starting the server."""
    try:
        version = metadata.version("mcp")
    except metadata.PackageNotFoundError:
        raise SdkIncompatible("sdk_not_installed") from None
    # Future major APIs must be investigated rather than silently attempted.
    if not re.fullmatch(r"[12]\.\d+\.\d+(?:[A-Za-z0-9.+-]{0,32})?", version):
        safe_version = version if re.fullmatch(r"\d+\.\d+\.\d+(?:[A-Za-z0-9.+-]{0,32})?", version) else "unrecognized"
        raise SdkIncompatible("unsupported_sdk_version", safe_version)
    try:
        from mcp import ClientSession, StdioServerParameters, types
        from mcp.client.stdio import stdio_client
        if "params" not in inspect.signature(ClientSession.list_tools).parameters:
            raise SdkIncompatible("list_tools_api_changed")
        fields = {
            "protocol": _model_field(types.InitializeResult, "protocol_version", "protocolVersion"),
            "cursor": _model_field(types.ListToolsResult, "next_cursor", "nextCursor"),
            "error": _model_field(types.CallToolResult, "is_error", "isError"),
            "structured": _model_field(types.CallToolResult, "structured_content", "structuredContent"),
            "schema": _model_field(types.Tool, "input_schema", "inputSchema"),
        }
        return {
            "ClientSession": ClientSession, "StdioServerParameters": StdioServerParameters,
            "stdio_client": stdio_client, "types": types, "fields": fields,
            "metadata": {"name": "mcp", "version": version,
                         "field_style": "snake_case" if fields["error"] == "is_error" else "camelCase"},
        }
    except SdkIncompatible as error:
        error.version = version
        raise
    except (ImportError, AttributeError, TypeError, ValueError):
        raise SdkIncompatible("sdk_client_api_unavailable", version) from None


def _credential_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            str(key).lower().replace("-", "_") not in CREDENTIAL_KEYS
            and _credential_free(item) for key, item in value.items()
        )
    return not isinstance(value, list) or all(_credential_free(item) for item in value)


def validate_plan(plan: Any) -> dict:
    """Validate configuration without evaluating or executing its contents."""
    if not isinstance(plan, dict) or set(plan) - {
        "command", "args", "required_tools", "cases", "timeout_seconds",
    }:
        raise ValueError("plan must use only documented fields")
    if not _credential_free(plan):
        raise ValueError("credentials belong in the process environment, not the plan")
    command = plan.get("command")
    if not isinstance(command, str) or not command or len(command) > 4096 or "\x00" in command or "://" in command:
        raise ValueError("command must name a local executable")
    arguments = plan.get("args", [])
    if not isinstance(arguments, list) or len(arguments) > 128 or any(
        not isinstance(arg, str) or len(arg) > 4096 or "\x00" in arg for arg in arguments
    ):
        raise ValueError("args must be a bounded list of strings")
    timeout = plan.get("timeout_seconds", 30)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 1 <= timeout <= 300:
        raise ValueError("timeout_seconds must be between 1 and 300")
    required = plan.get("required_tools", [])
    if not isinstance(required, list) or len(required) > 128 or any(
        not isinstance(name, str) or not NAME.fullmatch(name) for name in required
    ):
        raise ValueError("required_tools must contain tool names")
    cases = plan.get("cases", [])
    if not isinstance(cases, list) or len(cases) > 100:
        raise ValueError("cases must contain at most 100 cases")
    for case in cases:
        if not isinstance(case, dict) or set(case) - {"tool", "arguments", "expect", "match", "expect_error"}:
            raise ValueError("case must use only documented fields")
        if not isinstance(case.get("tool"), str) or not NAME.fullmatch(case["tool"]):
            raise ValueError("case must name a tool")
        if not isinstance(case.get("arguments", {}), dict):
            raise ValueError("case arguments must be an object")
        if type(case.get("expect_error", False)) is not bool:
            raise ValueError("expect_error must be a boolean")
        if case.get("match", "subset") not in ("subset", "exact"):
            raise ValueError("match must be subset or exact")
        if case.get("expect_error", False):
            if "expect" in case or "match" in case:
                raise ValueError("error cases cannot specify structured expectations")
        elif "expect" not in case or not isinstance(case["expect"], dict) or not case["expect"]:
            raise ValueError("success cases need a nonempty expected structured object")
    return plan


def matches(actual: Any, expected: Any, *, exact: bool = False) -> bool:
    """Object subset matching; arrays remain ordered and exact in length."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and (not exact or actual.keys() == expected.keys()) and all(
            key in actual and matches(actual[key], value, exact=exact) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            matches(left, right, exact=exact) for left, right in zip(actual, expected)
        )
    # JSON distinguishes a boolean from a number even though Python equates True and 1.
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    return actual == expected


async def check(plan: dict) -> dict:
    """Execute the validated plan and return metadata only, never result content."""
    validate_plan(plan)
    report = {
        "schema_version": 1, "ok": False, "protocol_connected": False,
        "validation_level": "protocol_only", "tool_count": 0,
        "case_count": len(plan.get("cases", [])), "cases": [],
        "client_sdk": None, "protocol_version": None,
        "limitations": [
            "Checks only the declared assertions; callers must choose meaningful real-software cases.",
            "No server identity, input, output, credential, or environment values are retained.",
            "The session timeout permits additional SDK process-cleanup time; it is not a hard wall-clock limit.",
        ],
    }
    previous_disable = logging.root.manager.disable
    # SDK diagnostics can include malformed server stdout. Keep it out of shared reports.
    logging.disable(logging.CRITICAL)
    try:
        try:
            sdk = _load_sdk()
        except SdkIncompatible as error:
            if error.version:
                report["client_sdk"] = {"name": "mcp", "version": error.version, "field_style": "unavailable"}
            report.update(failure="sdk_incompatible", sdk_issue=str(error), hint=SDK_HINT)
            return report
        report["client_sdk"] = sdk["metadata"]
        fields = sdk["fields"]
        params = sdk["StdioServerParameters"](
            command=plan["command"], args=plan.get("args", []), env=dict(os.environ),
        )
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with asyncio.timeout(plan.get("timeout_seconds", 30)):
                async with sdk["stdio_client"](params, errlog=errlog) as streams:
                    async with sdk["ClientSession"](*streams) as client:
                        initialized = await client.initialize()
                        report["protocol_connected"] = True
                        protocol = getattr(initialized, fields["protocol"])
                        # Protocol version originates at the server. Retain only
                        # a date-shaped value, never arbitrary server text.
                        report["protocol_version"] = protocol if re.fullmatch(r"\d{4}-\d{2}-\d{2}", protocol) else "unrecognized"
                        names: set[str] = set()
                        cursor = None
                        for _ in range(20):
                            listed = await client.list_tools(params=sdk["types"].PaginatedRequestParams(cursor=cursor))
                            names.update(tool.name for tool in listed.tools)
                            if any(not isinstance(getattr(tool, fields["schema"]), dict) for tool in listed.tools):
                                report["failure"] = "invalid_tool_schema"
                                return report
                            cursor = getattr(listed, fields["cursor"])
                            if not cursor:
                                break
                        else:
                            report["failure"] = "tool_pagination_limit"
                            return report
                        report["tool_count"] = len(names)
                        if not set(plan.get("required_tools", [])).issubset(names):
                            report["failure"] = "required_tool_missing"
                            return report
                        for index, case in enumerate(plan.get("cases", [])):
                            result = {"index": index, "ok": False, "expect_error": case.get("expect_error", False)}
                            report["cases"].append(result)
                            if case["tool"] not in names:
                                result["failure"] = "case_tool_missing"
                                continue
                            response = await client.call_tool(case["tool"], case.get("arguments", {}))
                            if not isinstance(response, sdk["types"].CallToolResult):
                                result["failure"] = "unsupported_tool_response"
                                continue
                            is_error = getattr(response, fields["error"])
                            if case.get("expect_error", False):
                                result["ok"] = bool(is_error)
                                if not result["ok"]:
                                    result["failure"] = "expected_error_not_returned"
                            elif is_error:
                                result["failure"] = "unexpected_tool_error"
                            else:
                                result["ok"] = matches(getattr(response, fields["structured"]), case["expect"], exact=case.get("match") == "exact")
                                if not result["ok"]:
                                    result["failure"] = "structured_result_mismatch"
                        report["ok"] = all(case["ok"] for case in report["cases"])
                        if report["cases"]:
                            report["validation_level"] = "declared_calls_checked"
                        return report
    except TimeoutError:
        report["ok"] = False
        report["failure"] = "timeout"
    except Exception:
        # Exception groups and transport errors may embed paths or server data.
        report["ok"] = False
        report["failure"] = "protocol_or_process_error"
    finally:
        logging.disable(previous_disable)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path, help="trusted local JSON plan; does not accept URLs")
    parser.add_argument("--output", type=Path, help="new report file; never overwrites an existing file")
    args = parser.parse_args()
    try:
        if args.output and args.output.exists():
            raise ValueError("report file already exists")
        if args.plan.stat().st_size > 1024 * 1024:
            raise ValueError("plan exceeds 1 MiB")
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON value")))
        validate_plan(plan)
        report = asyncio.run(check(plan))
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        else:
            print(serialized, end="")
    except (OSError, ValueError):
        print('{"ok": false, "failure": "invalid_plan_or_output"}', file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
