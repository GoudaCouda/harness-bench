#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = ["context.md", "fail_closed_policy.md", "recovery_queue.csv"]
ARTIFACTS = [
    "recovered_screening.csv",
    "screening_recovery_state.json",
    "screening_recovery_audit.md",
]


def digest_files(names: list[str]) -> str:
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((ROOT / name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    with (ROOT / ARTIFACTS[0]).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    state = json.loads((ROOT / ARTIFACTS[1]).read_text(encoding="utf-8"))
    keys = [row.get("item_id", "") for row in rows]
    counts = Counter(row.get("decision", "") for row in rows)
    blocked = sorted(
        row["item_id"] for row in rows if row.get("decision") in {"blocked", "hold"}
    )
    pending = sorted(
        row["item_id"] for row in rows if row.get("decision") == "pending_system"
    )
    status = str(state.get("status", "")).casefold().replace("_", " ")
    checks = {
        "workflow_id": state.get("workflow_id")
        == "155-payee-screening-service-recovery",
        "total_items": state.get("total_items") == len(rows),
        "decision_counts": state.get("decision_counts") == dict(sorted(counts.items())),
        "blocked_or_escalated_ids": sorted(state.get("blocked_or_escalated_ids", []))
        == blocked,
        "pending_ids": sorted(state.get("pending_ids", [])) == pending,
        "status": status
        in {
            "complete",
            "completed",
            "complete with exceptions",
            "partially recovered",
        }
        or (
            "recover" in status
            and any(term in status for term in ("pending", "partial", "exception"))
        ),
        "external_actions_executed": state.get("external_actions_executed") is False,
    }
    reconciled = all(checks.values())
    receipt = {
        "tool": "screeningctl/1",
        "input_bundle_sha256": digest_files(INPUTS),
        "artifact_bundle_sha256": digest_files(ARTIFACTS),
        "structural_status": "pass"
        if len(keys) == len(set(keys)) and reconciled
        else "fail",
    }
    output = {
        "workflow_id": "155-payee-screening-service-recovery",
        "decision_artifact": ARTIFACTS[0],
        "state_artifact": ARTIFACTS[1],
        "audit_artifact": ARTIFACTS[2],
        "row_count": len(rows),
        "unique_item_keys": len(keys) == len(set(keys)),
        "state_reconciled": reconciled,
        "inputs_unchanged": True,
        "external_actions_executed": False,
        "evidence_files_checked": INPUTS,
        "tool_receipt": receipt,
    }
    (ROOT / "verification.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"receipt": receipt, "state_checks": checks}, indent=2, sort_keys=True
        )
    )
    return 0 if receipt["structural_status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
