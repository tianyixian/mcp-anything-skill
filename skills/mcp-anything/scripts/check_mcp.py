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
"""
from __future__ import annotations

import argparse
import asyncio
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
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    validate_plan(plan)
    report = {
        "schema_version": 1, "ok": False, "protocol_connected": False,
        "validation_level": "protocol_only", "tool_count": 0,
        "case_count": len(plan.get("cases", [])), "cases": [],
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
        params = StdioServerParameters(
            command=plan["command"], args=plan.get("args", []), env=dict(os.environ),
        )
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with asyncio.timeout(plan.get("timeout_seconds", 30)):
                async with stdio_client(params, errlog=errlog) as streams:
                    async with ClientSession(*streams) as client:
                        await client.initialize()
                        report["protocol_connected"] = True
                        names: set[str] = set()
                        cursor = None
                        for _ in range(20):
                            listed = await client.list_tools(cursor=cursor)
                            names.update(tool.name for tool in listed.tools)
                            cursor = listed.nextCursor
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
                            result = {"index": index, "ok": False}
                            report["cases"].append(result)
                            if case["tool"] not in names:
                                result["failure"] = "case_tool_missing"
                                continue
                            response = await client.call_tool(case["tool"], case.get("arguments", {}))
                            if case.get("expect_error", False):
                                result["ok"] = bool(response.isError)
                                if not result["ok"]:
                                    result["failure"] = "expected_error_not_returned"
                            elif response.isError:
                                result["failure"] = "unexpected_tool_error"
                            else:
                                result["ok"] = matches(response.structuredContent, case["expect"], exact=case.get("match") == "exact")
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
