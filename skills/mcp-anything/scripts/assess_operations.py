"""Assess every requested operation against pinned MCP checks and outcome evidence.

This reads local evidence; it does not run software or establish its provenance.
Keep one ledger entry for every user-requested operation, including blockers.
See references/operation-acceptance.md for the schema and trust limits.
Exit codes: 0 all operations verified, 1 incomplete, 2 invalid ledger/output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any

IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
STATES = {"not_started", "discovered", "implemented", "blocked", "verified"}
MAX_BYTES = 16 * 1024 * 1024
MAX_FINITE_NUMBER = 1.7976931348623157e308


def finite_json(raw: bytes) -> Any:
    def reject(_: str) -> None:
        raise ValueError("nonfinite JSON")

    def finite_float(value: str) -> float:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite JSON")
        return result

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(raw.decode("utf-8-sig"), parse_constant=reject,
                      parse_float=finite_float, object_pairs_hook=unique_object)


def bounded_list(value: Any, maximum: int = 100, *, empty: bool = False) -> bool:
    return isinstance(value, list) and (empty or bool(value)) and len(value) <= maximum


def text_field(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 2000


def finite_number(value: Any) -> bool:
    """Accept JSON numbers representable as finite IEEE-754 values."""
    if type(value) not in (int, float):
        return False
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        return False
    return math.isfinite(converted) and abs(converted) <= MAX_FINITE_NUMBER


def valid_reference(value: Any, extra: set[str]) -> bool:
    return (
        isinstance(value, dict) and not set(value) - ({"path", "sha256"} | extra)
        and isinstance(value.get("path"), str) and 0 < len(value["path"]) <= 1024
        and isinstance(value.get("sha256"), str) and bool(DIGEST.fullmatch(value["sha256"]))
    )


def validate_ledger(ledger: Any) -> None:
    if (not isinstance(ledger, dict) or set(ledger) != {"schema_version", "operations"}
            or type(ledger["schema_version"]) is not int or ledger["schema_version"] != 1
            or not bounded_list(ledger["operations"])):
        raise ValueError("invalid ledger")
    ids: set[str] = set()
    for operation in ledger["operations"]:
        allowed = {"id", "request", "acceptance", "status", "blocker", "upstream_component",
                   "evidence_kind", "checks", "artifacts"}
        if not isinstance(operation, dict) or set(operation) - allowed:
            raise ValueError("invalid operation")
        key = operation.get("id")
        if not isinstance(key, str) or not IDENTIFIER.fullmatch(key) or key in ids:
            raise ValueError("operation IDs must be unique")
        ids.add(key)
        if not text_field(operation.get("request")) or not text_field(operation.get("acceptance")):
            raise ValueError("describe the request and its completion condition")
        if operation.get("status") not in STATES:
            raise ValueError("invalid operation status")
        if operation["status"] == "blocked" and not text_field(operation.get("blocker")):
            raise ValueError("blocked operations need a reason")
        if "evidence_kind" in operation and operation["evidence_kind"] not in {"real", "fixture", "analysis"}:
            raise ValueError("invalid evidence kind")
        if "upstream_component" in operation and not text_field(operation["upstream_component"]):
            raise ValueError("invalid upstream component")
        for field in ("checks", "artifacts"):
            if not bounded_list(operation.get(field, []), empty=True):
                raise ValueError("evidence lists must be bounded")
        for check in operation.get("checks", []):
            if (not valid_reference(check, {"cases"}) or not bounded_list(check.get("cases"))
                    or any(type(index) is not int or not 0 <= index < 100 for index in check["cases"])
                    or len(set(check["cases"])) != len(check["cases"])):
                raise ValueError("invalid check reference")
        for artifact in operation.get("artifacts", []):
            if not valid_reference(artifact, {"assertions"}) or not bounded_list(artifact.get("assertions", []), empty=True):
                raise ValueError("invalid outcome artifact")
            for assertion in artifact.get("assertions", []):
                if (not isinstance(assertion, dict) or set(assertion) - {"pointer", "equals", "approx", "atol", "rtol"}
                        or not isinstance(assertion.get("pointer"), str) or len(assertion["pointer"]) > 1024
                        or (assertion["pointer"] and not assertion["pointer"].startswith("/"))
                        or ("equals" in assertion) == ("approx" in assertion)):
                    raise ValueError("invalid outcome assertion")
                if "approx" in assertion:
                    for field in ("approx", "atol", "rtol"):
                        number = assertion.get(field, 0)
                        if not finite_number(number):
                            raise ValueError("numeric assertions need finite numbers")
                    if assertion.get("atol", 0) < 0 or assertion.get("rtol", 0) < 0:
                        raise ValueError("negative tolerance")
                elif "atol" in assertion or "rtol" in assertion:
                    raise ValueError("tolerance requires approx")


def read_reference(root: Path, reference: dict) -> bytes:
    relative = PurePosixPath(reference["path"])
    if (relative.is_absolute() or ".." in relative.parts or not relative.parts
            or any(char in reference["path"] for char in ("\\", ":", "\x00"))):
        raise ValueError("unsafe evidence path")
    target = root.joinpath(*relative.parts)
    for part in (target, *target.parents):
        if part == root:
            break
        metadata = part.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked evidence path")
    if not target.is_file() or target.stat().st_size > MAX_BYTES:
        raise ValueError("evidence size/type")
    with target.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("evidence hash/size")
    return raw


def at_pointer(document: Any, pointer: str) -> Any:
    if not pointer:
        return document
    value = document
    for part in pointer[1:].split("/"):
        if re.search(r"~(?![01])", part):
            raise ValueError("invalid JSON pointer")
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", part):
            value = value[int(part)]
        else:
            raise ValueError("missing JSON pointer")
    return value


def equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    return isinstance(actual, bool) == isinstance(expected, bool) and actual == expected


def outcome_matches(document: Any, assertion: dict) -> bool:
    actual = at_pointer(document, assertion["pointer"])
    if "equals" in assertion:
        return equal(actual, assertion["equals"])
    if not finite_number(actual) or not finite_number(assertion["approx"]):
        return False
    actual_float = float(actual)
    expected = float(assertion["approx"])
    atol = float(assertion.get("atol", 0))
    rtol = float(assertion.get("rtol", 0))
    tolerance = atol + rtol * abs(expected)
    # If the subtraction or tolerance overflows, fail closed instead of
    # treating an infinite error and infinite tolerance as a successful check.
    if not math.isfinite(tolerance):
        return False
    difference = abs(actual_float - expected)
    return math.isfinite(difference) and difference <= tolerance


def assess(ledger: dict, root: Path) -> dict:
    validate_ledger(ledger)
    root = root.resolve(strict=True)
    report = {"schema_version": 1, "complete": False, "operations": [], "limitations": [
        "Completeness is relative to the listed requests; retain every operation requested by the user.",
        "Real provenance, component choice and assertion relevance require review; hashes do not establish them.",
        "No software is executed and no input/output values or blocker text are copied into this summary.",
    ]}
    for operation in ledger["operations"]:
        result = {"id": operation["id"], "status": operation["status"], "verified": False}
        report["operations"].append(result)
        if operation["status"] != "verified":
            result["reason"] = "requested_operation_incomplete"
            continue
        result["status"] = "unverified"
        if operation.get("evidence_kind") != "real":
            result["reason"] = "real_execution_evidence_required"
            continue
        if not operation.get("upstream_component") or not operation.get("checks") or not operation.get("artifacts"):
            result["reason"] = "operation_evidence_missing"
            continue
        try:
            positive_calls = 0
            for check in operation["checks"]:
                checked = finite_json(read_reference(root, check))
                if (checked.get("schema_version") != 1 or checked.get("ok") is not True
                        or checked.get("protocol_connected") is not True
                        or checked.get("validation_level") != "declared_calls_checked"):
                    raise ValueError("MCP check incomplete")
                for index in check["cases"]:
                    case = checked["cases"][index]
                    if case.get("index") != index or case.get("ok") is not True or type(case.get("expect_error")) is not bool:
                        raise ValueError("case failed or unsupported old report")
                    positive_calls += not case["expect_error"]
            if not positive_calls:
                result["reason"] = "positive_operation_call_required"
                continue
            if not any(artifact.get("assertions") for artifact in operation["artifacts"]):
                result["reason"] = "outcome_assertion_required"
                continue
            for artifact in operation["artifacts"]:
                raw = read_reference(root, artifact)
                assertions = artifact.get("assertions", [])
                if assertions and not all(outcome_matches(finite_json(raw), assertion) for assertion in assertions):
                    result["reason"] = "outcome_assertion_failed"
                    break
            else:
                result.update(status="verified", verified=True)
                continue
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, OverflowError):
            result["reason"] = "evidence_invalid_or_check_failed"
    report["complete"] = all(item["verified"] for item in report["operations"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="local JSON ledger; evidence paths are relative to this file")
    parser.add_argument("--output", type=Path, help="new summary file; never overwrite")
    args = parser.parse_args()
    try:
        if args.output and args.output.exists():
            raise ValueError("output exists")
        with args.ledger.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("ledger exceeds 1 MiB")
        report = assess(finite_json(raw), args.ledger.parent)
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        else:
            print(serialized, end="")
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        print('{"complete": false, "failure": "invalid_ledger_or_output"}', file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(0 if report["complete"] else 1)


if __name__ == "__main__":
    main()
