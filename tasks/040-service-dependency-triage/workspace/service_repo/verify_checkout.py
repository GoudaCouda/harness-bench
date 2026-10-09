#!/usr/bin/env python3
"""Offline auth-gateway behavior verifier used by the incident exercise."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def evaluate(config: dict[str, Any], case: dict[str, Any]) -> tuple[str, str]:
    allowed_issuers = config.get("allowed_issuers")
    accepted_audiences = config.get("accepted_audiences")
    jwks_keys = config.get("jwks_keys")
    if not isinstance(allowed_issuers, list):
        return "deny", "invalid allowed_issuers configuration"
    if not isinstance(accepted_audiences, list):
        return "deny", "invalid accepted_audiences configuration"
    if not isinstance(jwks_keys, dict):
        return "deny", "invalid jwks_keys configuration"

    issuer = case.get("issuer")
    audience = case.get("audience")
    kid = case.get("kid")
    if issuer not in allowed_issuers:
        return "deny", "issuer_not_allowed"
    if audience not in accepted_audiences:
        return "deny", "audience_not_allowed"
    issuer_keys = jwks_keys.get(issuer, [])
    if not isinstance(issuer_keys, list) or kid not in issuer_keys:
        return "deny", "signing_key_not_found"
    if config.get("fail_closed") is not True:
        return "deny", "validator_not_fail_closed"
    return "allow", "validated"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("auth_gateway_config.json"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("fixtures") / "token_cases.json",
    )
    args = parser.parse_args()

    config = _load_object(args.config)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError(f"{args.cases} must contain a JSON array")

    results = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every case must be a JSON object")
        actual, reason = evaluate(config, case)
        expected = case.get("expected")
        results.append(
            {
                "case_id": case.get("case_id"),
                "expected": expected,
                "actual": actual,
                "reason": reason,
                "pass": actual == expected,
            }
        )

    passed = sum(bool(row["pass"]) for row in results)
    report = {
        "status": "pass" if passed == len(results) else "fail",
        "passed": passed,
        "total": len(results),
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
