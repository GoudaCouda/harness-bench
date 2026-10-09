#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def write(name: str, value: object) -> None:
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def status() -> int:
    state = load("pki_state.json")
    services = load("services.json")["services"]
    print(
        json.dumps(
            {
                "revision": state.get("revision"),
                "services": {
                    key: {
                        "expected_leaf": services[key]["expected_leaf"],
                        "presented_chain": row.get("presented_chain"),
                        "truststore": row.get("truststore"),
                        "rotation_scope": services[key]["rotation_scope"],
                    }
                    for key, row in state.get("services", {}).items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def apply(plan_name: str) -> int:
    plan = load(plan_name)
    state = load("pki_state.json")
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        print("plan must contain a non-empty actions array")
        return 2
    plan_sha = digest(plan)
    audit_path = ROOT / "pki_audit.jsonl"
    existing = []
    if audit_path.is_file():
        existing = [
            json.loads(line) for line in audit_path.read_text().splitlines() if line
        ]
    if any(row.get("plan_sha256") == plan_sha for row in existing):
        print(
            json.dumps(
                {
                    "status": "idempotent",
                    "revision": state.get("revision"),
                    "plan_sha256": plan_sha,
                },
                indent=2,
            )
        )
        return 0
    before = json.loads(json.dumps(state))
    changed: list[str] = []
    seen: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            print("every action must be an object")
            return 2
        service_id = str(action.get("service_id") or "")
        if service_id in seen or service_id not in state.get("services", {}):
            print(f"unknown or duplicate service action: {service_id}")
            return 2
        seen.add(service_id)
        row = state["services"][service_id]
        chain = action.get("presented_chain")
        adds = action.get("truststore_add", [])
        removes = action.get("truststore_remove", [])
        if (
            not isinstance(chain, list)
            or len(chain) != 2
            or not isinstance(adds, list)
            or not isinstance(removes, list)
        ):
            print(f"invalid action schema for {service_id}")
            return 2
        updated = {
            "presented_chain": [str(value) for value in chain],
            "truststore": sorted(
                (set(row.get("truststore", [])) | set(map(str, adds)))
                - set(map(str, removes))
            ),
        }
        if updated != row:
            state["services"][service_id] = updated
            changed.append(service_id)
    if changed:
        state["revision"] = int(state.get("revision", 0)) + 1
        write("pki_state.json", state)
        receipt = {
            "tool": "pki_ctl/1",
            "revision": state["revision"],
            "plan_sha256": plan_sha,
            "before_state_sha256": digest(before),
            "after_state_sha256": digest(state),
            "changed_services": sorted(changed),
        }
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
        print(json.dumps({"status": "applied", **receipt}, indent=2, sort_keys=True))
    else:
        print(
            json.dumps(
                {"status": "no_change", "revision": state.get("revision")}, indent=2
            )
        )
    return 0


def verify() -> int:
    state = load("pki_state.json")
    certs_doc = load("certificates.json")
    certs = certs_doc["certificates"]
    services = load("services.json")["services"]
    now = datetime.fromisoformat(certs_doc["as_of"].replace("Z", "+00:00"))
    checks: dict[str, bool] = {}
    for service_id, spec in services.items():
        row = state.get("services", {}).get(service_id, {})
        chain = row.get("presented_chain", [])
        leaf = certs.get(chain[0], {}) if len(chain) == 2 else {}
        intermediate = certs.get(chain[1], {}) if len(chain) == 2 else {}
        root_id = intermediate.get("issuer")
        checks[f"{service_id}:expected_leaf"] = (
            bool(chain) and chain[0] == spec["expected_leaf"]
        )
        checks[f"{service_id}:subject"] = leaf.get("subject") == spec["dns_name"]
        checks[f"{service_id}:chain"] = leaf.get("issuer") == (
            chain[1] if len(chain) == 2 else None
        )
        checks[f"{service_id}:root_trusted"] = root_id in row.get("truststore", [])
        try:
            checks[f"{service_id}:not_expired"] = datetime.fromisoformat(
                str(leaf.get("not_after", "")).replace("Z", "+00:00")
            ) > now
        except ValueError:
            checks[f"{service_id}:not_expired"] = False
    checks["overlap:root-2024-retained"] = all(
        "root-2024" in state["services"][key]["truststore"]
        for key in ("billing-api", "event-worker", "reporting")
    )
    checks["audit:single-transition"] = (
        (ROOT / "pki_audit.jsonl").is_file()
        and len(
            [
                line
                for line in (ROOT / "pki_audit.jsonl").read_text().splitlines()
                if line
            ]
        )
        == 1
    )
    report = {
        "tool": "pki_ctl/1",
        "status": "pass" if all(checks.values()) else "fail",
        "state_sha256": digest(state),
        "checks": checks,
    }
    write("handshake_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("plan")
    sub.add_parser("verify")
    args = parser.parse_args()
    if args.command == "status":
        return status()
    if args.command == "apply":
        return apply(args.plan)
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
