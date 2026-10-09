#!/usr/bin/env python3
"""Offline WAF replay and local staging controller."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
POLICY = ROOT / "waf_policy.json"
CORPUS = ROOT / "traffic_corpus.json"
SIGNERS = ROOT / "trusted_signers.json"
REPORT = ROOT / "replay_report.json"
CHANGE = ROOT / "change_record.md"
STATE = ROOT / ".waf_stage_state.json"
RECEIPT = ROOT / "waf_stage_receipt.json"
SOURCE_HASHES = {
    "incident.md": "d661ee6ef4864524bd1ce5fb7f3e031462926cb578af0667eeac44b2c1d66f89",
    "policy.md": "0c1e499102f8df02e4a827dba509457333ec683ddecd356aeed1cd1c0597c922",
    "trusted_signers.json": "dcbef77885197b28756f4a3fe22c1ca01c58c54d514b4b06e11b40bf7a9a7c65",
    "baseline_snapshot.json": "d3b07e4a6c84c20c89f05fc10cfb2083f987d7701a0ea26c594420b0399d46cd",
    "traffic_corpus.json": "5ceb644d94295a42219603fbb6f008f274a786934323942dd86565c5345e83ac",
    "waf_policy_seed.json": "d40474485642496edabd56ae5bf05d4070522b66379e9b431f92c3c6e5eb0a95",
}
RULE_IDS = {
    "TRAVERSAL-930100",
    "RCE-932100",
    "SQLI-942100",
    "RATE-LOGIN-100",
}
EXCLUSION_KEYS = {"rule_id", "method", "path", "field", "verified_signer"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _source_errors() -> list[str]:
    errors: list[str] = []
    for name, expected in SOURCE_HASHES.items():
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            errors.append(f"protected source missing or symlinked: {name}")
        elif _sha256(path) != expected:
            errors.append(f"protected source changed: {name}")
    return errors


def _policy_errors(policy: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return ["waf_policy.json must be one JSON object"]
    if set(policy) != {"schema_version", "policy_id", "revision", "rules", "exclusions"}:
        errors.append("policy top-level keys are noncanonical")
    if policy.get("schema_version") != 1 or policy.get("policy_id") != "gateway-waf-2026-08":
        errors.append("schema_version or policy_id changed")
    revision = policy.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 7:
        errors.append("policy revision must be an integer at least 7")
    rules = policy.get("rules")
    if not isinstance(rules, dict) or set(rules) != RULE_IDS:
        errors.append("exactly the four published rule IDs must remain")
        return errors
    seed_rules = _read_json(ROOT / "waf_policy_seed.json")["rules"]
    for rule_id, rule in rules.items():
        if not isinstance(rule, dict):
            errors.append(f"{rule_id} must be an object")
            continue
        if rule.get("enabled") is not True:
            errors.append(f"{rule_id} must remain enabled")
        status = rule.get("block_status")
        if not isinstance(status, int) or isinstance(status, bool):
            errors.append(f"{rule_id}.block_status must be an integer")
    traversal = rules.get("TRAVERSAL-930100", {})
    if set(traversal) != {"enabled", "path_prefix", "decode_passes", "block_status"}:
        errors.append("TRAVERSAL-930100 keys are noncanonical")
    if not isinstance(traversal.get("path_prefix"), str) or not isinstance(
        traversal.get("decode_passes"), int
    ):
        errors.append("traversal path_prefix/decode_passes have invalid types")
    if any(
        traversal.get(field) != seed_rules["TRAVERSAL-930100"][field]
        for field in ("enabled", "path_prefix", "block_status")
    ):
        errors.append("TRAVERSAL-930100 baseline scope or action changed")
    for rule_id in ("RCE-932100", "SQLI-942100"):
        rule = rules.get(rule_id, {})
        required = (
            {"enabled", "keywords", "fields", "block_status"}
            if rule_id == "RCE-932100"
            else {"enabled", "keywords", "decode_passes", "block_status"}
        )
        if set(rule) != required:
            errors.append(f"{rule_id} keys are noncanonical")
        if not isinstance(rule.get("keywords"), list) or not all(
            isinstance(item, str) and item for item in rule.get("keywords", [])
        ):
            errors.append(f"{rule_id}.keywords must be nonempty strings")
        if rule != seed_rules[rule_id]:
            errors.append(f"{rule_id} baseline definition changed")
    rate = rules.get("RATE-LOGIN-100", {})
    if set(rate) != {
        "enabled", "method", "path", "window_seconds", "threshold", "key", "block_status"
    }:
        errors.append("RATE-LOGIN-100 keys are noncanonical")
    for field in ("window_seconds", "threshold"):
        if not isinstance(rate.get(field), int) or isinstance(rate.get(field), bool):
            errors.append(f"RATE-LOGIN-100.{field} must be an integer")
    if any(
        rate.get(field) != seed_rules["RATE-LOGIN-100"][field]
        for field in ("enabled", "method", "path", "window_seconds", "key", "block_status")
    ):
        errors.append("RATE-LOGIN-100 baseline scope, key, window, or action changed")
    exclusions = policy.get("exclusions")
    if not isinstance(exclusions, list) or len(exclusions) > 4:
        errors.append("exclusions must be an array of at most four scoped local objects")
    else:
        seen: set[tuple[str, ...]] = set()
        for index, exclusion in enumerate(exclusions):
            if not isinstance(exclusion, dict) or set(exclusion) != EXCLUSION_KEYS:
                errors.append(f"exclusions[{index}] keys are noncanonical")
                continue
            values = tuple(str(exclusion.get(key, "")) for key in sorted(EXCLUSION_KEYS))
            if not all(values) or values in seen:
                errors.append(f"exclusions[{index}] is empty or duplicated")
            seen.add(values)
            if exclusion.get("rule_id") not in RULE_IDS:
                errors.append(f"exclusions[{index}] names an unknown rule")
            if not str(exclusion.get("field", "")).startswith("body."):
                errors.append(f"exclusions[{index}].field must be one body field")
    return errors


def _canonical_body(request: dict[str, Any]) -> bytes:
    return json.dumps(
        request.get("body") or {}, sort_keys=True, separators=(",", ":")
    ).encode()


def _signer_map() -> dict[str, dict[str, str]]:
    payload = _read_json(SIGNERS)
    return {
        str(row["key_id"]): row
        for row in payload.get("signers", [])
        if isinstance(row, dict)
    }


def _prepare_request(request: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(request))
    headers = clone.setdefault("headers", {})
    if headers.get("X-Vendor-Signature") == "__AUTO__":
        key = _signer_map().get(str(headers.get("X-Vendor-Key-ID", "")), {})
        signature = hmac.new(
            str(key.get("secret", "")).encode(), _canonical_body(clone), hashlib.sha256
        ).hexdigest()
        headers["X-Vendor-Signature"] = f"sha256={signature}"
    return clone


def _verified_signer(request: dict[str, Any]) -> str:
    headers = request.get("headers") or {}
    key_id = str(headers.get("X-Vendor-Key-ID", ""))
    supplied = str(headers.get("X-Vendor-Signature", ""))
    key = _signer_map().get(key_id)
    if not key or key.get("state") != "active" or key.get("algorithm") != "hmac-sha256":
        return ""
    expected = "sha256=" + hmac.new(
        str(key["secret"]).encode(), _canonical_body(request), hashlib.sha256
    ).hexdigest()
    return key_id if hmac.compare_digest(supplied, expected) else ""


def _excluded(
    policy: dict[str, Any], request: dict[str, Any], rule_id: str, field: str
) -> bool:
    signer = _verified_signer(request)
    return any(
        exclusion.get("rule_id") == rule_id
        and exclusion.get("method") == request.get("method")
        and exclusion.get("path") == request.get("path")
        and exclusion.get("field") == field
        and exclusion.get("verified_signer") == signer
        and bool(signer)
        for exclusion in policy.get("exclusions", [])
    )


def _decode(value: str, passes: int) -> str:
    result = value
    for _ in range(max(0, min(passes, 4))):
        result = unquote(result)
    return result


def _result(action: str, status: int, rule_id: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"action": action, "status": status}
    if rule_id:
        result["rule_id"] = rule_id
    return result


def _evaluate(
    policy: dict[str, Any], request: dict[str, Any], windows: dict[str, deque[int]]
) -> dict[str, Any]:
    rules = policy["rules"]
    traversal = rules["TRAVERSAL-930100"]
    path = str(request.get("path", ""))
    if traversal["enabled"] and path.startswith(str(traversal["path_prefix"])):
        decoded = _decode(path, int(traversal["decode_passes"]))
        if "../" in decoded or "..\\" in decoded:
            return _result("block", int(traversal["block_status"]), "TRAVERSAL-930100")

    rce = rules["RCE-932100"]
    body = request.get("body") or {}
    if rce["enabled"]:
        for field in rce["fields"]:
            name = str(field).removeprefix("body.")
            value = str(body.get(name, ""))
            if value and any(word.casefold() in value.casefold() for word in rce["keywords"]):
                if not _excluded(policy, request, "RCE-932100", str(field)):
                    return _result("block", int(rce["block_status"]), "RCE-932100")

    sqli = rules["SQLI-942100"]
    if sqli["enabled"]:
        decoded = _decode(path, int(sqli["decode_passes"]))
        if any(word.casefold() in decoded.casefold() for word in sqli["keywords"]):
            return _result("block", int(sqli["block_status"]), "SQLI-942100")

    rate = rules["RATE-LOGIN-100"]
    if (
        rate["enabled"]
        and request.get("method") == rate["method"]
        and path == rate["path"]
    ):
        key = str(request.get(str(rate["key"]), ""))
        now = int(request.get("at", 0))
        queue = windows[key]
        cutoff = now - int(rate["window_seconds"])
        while queue and queue[0] <= cutoff:
            queue.popleft()
        queue.append(now)
        if len(queue) > int(rate["threshold"]):
            return _result("block", int(rate["block_status"]), "RATE-LOGIN-100")

    return _result("allow", 200)


def _run_replay(policy: dict[str, Any]) -> dict[str, Any]:
    corpus = _read_json(CORPUS)
    windows: dict[str, deque[int]] = defaultdict(deque)
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for raw in corpus.get("requests", []):
        request = _prepare_request(raw)
        observed = _evaluate(policy, request, windows)
        expected = raw.get("expected") or {}
        passed = observed == expected
        if not passed:
            failures.append(str(raw.get("id", "")))
        results.append(
            {
                "request_id": raw.get("id"),
                "expected": expected,
                "observed": observed,
                "pass": passed,
            }
        )
    return {
        "schema_version": 1,
        "corpus_id": corpus.get("corpus_id"),
        "policy_id": policy.get("policy_id"),
        "policy_revision": policy.get("revision"),
        "policy_sha256": _sha256(POLICY),
        "corpus_sha256": _sha256(CORPUS),
        "total": len(results),
        "passed": sum(bool(row["pass"]) for row in results),
        "failed": len(failures),
        "failed_request_ids": failures,
        "policy_passed": not failures,
        "external_actions_executed": False,
        "results": results,
    }


def _load_policy() -> tuple[dict[str, Any], list[str]]:
    try:
        policy = _read_json(POLICY)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"cannot read waf_policy.json: {exc}"]
    return policy, _source_errors() + _policy_errors(policy)


def _report_is_current(policy: dict[str, Any]) -> bool:
    try:
        report = _read_json(REPORT)
    except (OSError, json.JSONDecodeError):
        return False
    return report == _run_replay(policy) and report.get("policy_passed") is True


def _bundle_hash() -> str:
    payload = json.dumps(SOURCE_HASHES, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _stage_objects(policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    revision = int(policy["revision"])
    token_raw = "\n".join(
        (
            "waf-policy-local-stage-v1",
            _bundle_hash(),
            _sha256(POLICY),
            _sha256(REPORT),
            _sha256(CHANGE),
            str(revision),
        )
    ).encode()
    token = hashlib.sha256(token_raw).hexdigest()
    state = {
        "schema_version": 1,
        "stage_id": "gateway-waf-repair",
        "phase": "staged_for_security_review",
        "policy_revision": revision,
        "source_bundle_sha256": _bundle_hash(),
        "policy_sha256": _sha256(POLICY),
        "replay_report_sha256": _sha256(REPORT),
        "change_record_sha256": _sha256(CHANGE),
        "stage_token": token,
        "external_deployment_executed": False,
    }
    receipt = {
        "receipt_type": "local_waf_policy_stage",
        "stage_id": state["stage_id"],
        "phase": state["phase"],
        "policy_revision": revision,
        "source_bundle_sha256": state["source_bundle_sha256"],
        "policy_sha256": state["policy_sha256"],
        "replay_report_sha256": state["replay_report_sha256"],
        "change_record_sha256": state["change_record_sha256"],
        "stage_token": token,
        "external_deployment_executed": False,
    }
    return state, receipt


def command_status(_: argparse.Namespace) -> int:
    policy, errors = _load_policy()
    output = {
        "policy_revision": policy.get("revision"),
        "configuration_valid": not errors,
        "current_replay_passed": bool(policy) and not errors and _report_is_current(policy),
        "staged": STATE.is_file() and RECEIPT.is_file(),
        "errors": errors,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_inspect(args: argparse.Namespace) -> int:
    policy, errors = _load_policy()
    if errors:
        print(json.dumps({"errors": errors}, indent=2), file=sys.stderr)
        return 1
    corpus = _read_json(CORPUS)
    target = next(
        (row for row in corpus.get("requests", []) if row.get("id") == args.request_id),
        None,
    )
    if target is None:
        print(f"unknown request ID: {args.request_id}", file=sys.stderr)
        return 2
    windows: dict[str, deque[int]] = defaultdict(deque)
    observed: dict[str, Any] = {}
    for raw in corpus.get("requests", []):
        observed = _evaluate(policy, _prepare_request(raw), windows)
        if raw is target:
            break
    print(json.dumps({"request": target, "observed": observed}, indent=2, sort_keys=True))
    return 0


def command_replay(_: argparse.Namespace) -> int:
    policy, errors = _load_policy()
    if errors:
        print(json.dumps({"errors": errors}, indent=2), file=sys.stderr)
        return 1
    report = _run_replay(policy)
    _write_json(REPORT, report)
    print(
        json.dumps(
            {
                "total": report["total"],
                "passed": report["passed"],
                "failed_request_ids": report["failed_request_ids"],
                "report": REPORT.name,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["policy_passed"] else 1


def command_validate(_: argparse.Namespace) -> int:
    policy, errors = _load_policy()
    if isinstance(policy.get("revision"), int) and policy.get("revision") <= 7:
        errors.append("a staged repair must increment revision 7")
    if isinstance(policy.get("exclusions"), list) and len(policy["exclusions"]) != 1:
        errors.append("the staged repair requires exactly one scoped local exclusion")
    if not errors and not _report_is_current(policy):
        errors.append("replay_report.json is absent, stale, or has failing cases")
    if not CHANGE.is_file() or CHANGE.is_symlink() or CHANGE.stat().st_size < 500:
        errors.append("change_record.md must be a reviewable file of at least 500 bytes")
    else:
        low = CHANGE.read_text(encoding="utf-8", errors="replace").casefold()
        for term in (
            "verified signer",
            "two",
            "client_ip",
            "sql",
            "regression",
            "offline",
            "security review",
        ):
            if term not in low:
                errors.append(f"change_record.md omits required topic: {term}")
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_stage(args: argparse.Namespace) -> int:
    if command_validate(args):
        return 1
    policy = _read_json(POLICY)
    state, receipt = _stage_objects(policy)
    _write_json(STATE, state)
    _write_json(RECEIPT, receipt)
    print(json.dumps({"staged": True, "stage_token": state["stage_token"]}, indent=2))
    return 0


def command_verify_stage(_: argparse.Namespace) -> int:
    policy, errors = _load_policy()
    if errors or not _report_is_current(policy):
        errors.append("policy or replay is not currently valid")
    if not CHANGE.is_file():
        errors.append("change_record.md is missing")
    if not errors:
        expected_state, expected_receipt = _stage_objects(policy)
        try:
            state = _read_json(STATE)
            receipt = _read_json(RECEIPT)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"stage state or receipt unreadable: {exc}")
        else:
            if state != expected_state:
                errors.append("stage state is stale or noncanonical")
            if receipt != expected_receipt:
                errors.append("stage receipt is stale or noncanonical")
    print(json.dumps({"stage_valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show policy, replay, and stage state").set_defaults(func=command_status)
    inspect_parser = subparsers.add_parser("inspect", help="inspect one public replay request")
    inspect_parser.add_argument("--request-id", required=True)
    inspect_parser.set_defaults(func=command_inspect)
    subparsers.add_parser("replay", help="run the public replay and write replay_report.json").set_defaults(func=command_replay)
    subparsers.add_parser("validate", help="validate policy, replay, and change record").set_defaults(func=command_validate)
    subparsers.add_parser("stage", help="create a local hash-bound stage receipt").set_defaults(func=command_stage)
    subparsers.add_parser("verify-stage", help="verify current stage hashes and receipt").set_defaults(func=command_verify_stage)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
