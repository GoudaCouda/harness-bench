#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from risklib import canonical_sha, load, statement_payload, statement_reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify supplier VEX assertions against this release")
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--statement")
    args = parser.parse_args()
    vex = load("evidence/supplier.vex.json")
    sbom = load("evidence/release.cdx.json")
    policy = load("policy/release_policy.json")
    trust = load("evidence/trust_store.json")
    components = {str(row["purl"]): row for row in sbom.get("components", [])}
    rows = vex.get("statements", [])
    if args.statement:
        rows = [row for row in rows if row.get("statement_id") == args.statement]
        if not rows:
            parser.error(f"unknown statement: {args.statement}")
    results = []
    for statement in rows:
        vulnerability_id = str(statement.get("vulnerability_id"))
        stated_purl = str(statement.get("component_purl"))
        exact = stated_purl if stated_purl in components else None
        if exact is None:
            base = stated_purl.rpartition("@")[0]
            alternatives = sorted(purl for purl in components if purl.rpartition("@")[0] == base)
            target = alternatives[0] if len(alternatives) == 1 else stated_purl
        else:
            alternatives = [exact]
            target = exact
        reasons = statement_reasons(statement, target, vulnerability_id, policy, trust)
        results.append(
            {
                "statement_id": statement.get("statement_id"),
                "vulnerability_id": vulnerability_id,
                "stated_component_purl": stated_purl,
                "matching_release_components": alternatives,
                "accepted": not reasons,
                "reasons": reasons,
                "provided_payload_sha256": statement.get("payload_sha256"),
                "computed_payload_sha256": canonical_sha(statement_payload(statement)),
                "status": statement.get("status"),
            }
        )
    print(json.dumps({"document_id": vex.get("document_id"), "results": results}, indent=2, sort_keys=True))
    return 0 if all(row["accepted"] for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
