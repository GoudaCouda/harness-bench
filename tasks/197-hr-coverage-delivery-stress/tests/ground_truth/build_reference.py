#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
SEED = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def run(workspace: Path, command: str, plan: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "continuancectl.py", command, plan], cwd=workspace,
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refs(case_id: str, notice_id: str | None, event_ids: list[str], receipt_ids: list[str]) -> list[str]:
    values = {
        f"state/continuance.db#case:{case_id}",
        f"state/stale_checkpoint.json#cases/{case_id}",
        "policy/continuance_policy.json#decision_precedence",
    }
    if notice_id:
        values.add(f"state/continuance.db#notices:{notice_id}")
    values.update(f"evidence/eligibility_events.jsonl#event:{item}" for item in event_ids)
    values.update(f"evidence/delivery_receipts.jsonl#receipt:{item}" for item in receipt_ids)
    return sorted(values)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hb197-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(SEED, workspace)
        inspected = subprocess.run(["python3", "continuancectl.py", "inspect"], cwd=workspace, check=True, text=True, stdout=subprocess.PIPE)
        checkpoint = json.loads(inspected.stdout)["source_checkpoint"]
        decisions = [
            {"case_id": "COV-7201", "baseline_state": "drafted", "disposition": "rebuild_beneficiary_notice", "notice_version": 2, "address_version": 1, "beneficiary_keys": ["P-7201-E", "P-7201-S"], "delivery_evidence": "none", "deadline_state": "open", "next_local_action": "stage_corrected_notice", "evidence_refs": refs("COV-7201", "NOTICE-7201", ["EV-7201-BEN3", "EV-7201-QUAL"], [])},
            {"case_id": "COV-7202", "baseline_state": "delivery_timeout", "disposition": "preserve_delivered", "notice_version": 1, "address_version": 2, "beneficiary_keys": ["P-7202-E"], "delivery_evidence": "evidence/delivery_receipts.jsonl#receipt:RCPT-7202-D", "deadline_state": "satisfied", "next_local_action": "none", "evidence_refs": refs("COV-7202", "NOTICE-7202", [], ["RCPT-7202-D", "RCPT-7202-T"])},
            {"case_id": "COV-7203", "baseline_state": "returned", "disposition": "reissue_to_verified_address", "notice_version": 2, "address_version": 2, "beneficiary_keys": ["P-7203-C", "P-7203-E"], "delivery_evidence": "evidence/delivery_receipts.jsonl#receipt:RCPT-7203-R", "deadline_state": "open", "next_local_action": "stage_reissue_package", "evidence_refs": refs("COV-7203", "NOTICE-7203", ["EV-7203-ADDR2", "EV-7203-REPLAY"], ["RCPT-7203-R"])},
            {"case_id": "COV-7204", "baseline_state": "delivery_timeout", "disposition": "hold_delivery_investigation", "notice_version": 1, "address_version": 1, "beneficiary_keys": ["P-7204-S"], "delivery_evidence": "evidence/delivery_receipts.jsonl#receipt:RCPT-7204-A", "deadline_state": "open", "next_local_action": "investigate_provider_receipt", "evidence_refs": refs("COV-7204", "NOTICE-7204", [], ["RCPT-7204-A", "RCPT-7204-T"])},
            {"case_id": "COV-7205", "baseline_state": "elected", "disposition": "preserve_post_notice_state", "notice_version": 2, "address_version": 2, "beneficiary_keys": ["P-7205-E"], "delivery_evidence": "evidence/delivery_receipts.jsonl#receipt:RCPT-7205-D", "deadline_state": "satisfied", "next_local_action": "none", "evidence_refs": refs("COV-7205", "NOTICE-7205", ["EV-7205-ELECT"], ["RCPT-7205-D"])},
            {"case_id": "COV-7206", "baseline_state": "drafted", "disposition": "hold_identity_conflict", "notice_version": 1, "address_version": 1, "beneficiary_keys": ["P-7206-E"], "delivery_evidence": "none", "deadline_state": "open", "next_local_action": "resolve_identity", "evidence_refs": refs("COV-7206", "NOTICE-7206", ["EV-7206-COLLIDE"], [])},
            {"case_id": "COV-7207", "baseline_state": "eligible_unsent", "disposition": "escalate_deadline_review", "notice_version": 1, "address_version": 1, "beneficiary_keys": ["P-7207-E"], "delivery_evidence": "none", "deadline_state": "expired", "next_local_action": "stage_compliance_review", "evidence_refs": refs("COV-7207", None, ["EV-7207-QUAL"], [])},
        ]
        plan = {
            "schema_version": 1, "recovery_id": "CONT-REC-2026-08-14",
            "source_checkpoint": checkpoint, "as_of": "2026-08-14T16:00:00Z",
            "case_decisions": decisions,
            "journal_actions": [
                {"journal_id": "J-OLD-CASE-7203", "table_name": "cases", "record_id": "COV-7203", "action": "restore_before_image"},
                {"journal_id": "J-OLD-QUEUE-7203", "table_name": "recovery_queue", "record_id": "Q-PARTIAL-7203", "action": "remove_partial_insert"},
            ],
            "queue_totals": {"corrected_notice": 1, "reissue": 1, "delivery_investigation": 1, "compliance_review": 1},
            "external_notices_sent": False, "coverage_changed": False,
        }
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for command in ("preview", "apply", "verify", "stage"):
            completed = run(workspace, command, "recovery_plan.json")
            if completed.returncode:
                raise RuntimeError(f"{command} failed:\n{completed.stdout}")
        equivalent = json.loads(json.dumps(plan))
        equivalent["case_decisions"].reverse()
        equivalent["journal_actions"].reverse()
        for row in equivalent["case_decisions"]:
            row["beneficiary_keys"].reverse()
            row["evidence_refs"] = [value.replace("#case:", "#cases:").replace("#event:", "#event_id:") for value in reversed(row["evidence_refs"])]
        (workspace / "equivalent_recovery_plan.json").write_text(json.dumps(equivalent, indent=4) + "\n", encoding="utf-8")
        completed = run(workspace, "replay", "equivalent_recovery_plan.json")
        if completed.returncode:
            raise RuntimeError(f"replay failed:\n{completed.stdout}")
        conflict = json.loads(json.dumps(plan))
        next(row for row in conflict["case_decisions"] if row["case_id"] == "COV-7204")["next_local_action"] = "stage_reissue_package"
        (workspace / "conflict_probe_plan.json").write_text(json.dumps(conflict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tracked = {
            "database": workspace / "state/continuance.db",
            "bundle": workspace / "staging/notice_review_queue.json",
            "manifest": workspace / "staging/queue_manifest.json",
            "receipt": workspace / "state/staging_receipt.json",
        }
        before = {name: sha(path) for name, path in tracked.items()}
        completed = run(workspace, "apply", "conflict_probe_plan.json")
        after = {name: sha(path) for name, path in tracked.items()}
        conflict_probe = {
            "schema_version": 1,
            "command": "python3 continuancectl.py apply conflict_probe_plan.json",
            "exit_code": completed.returncode,
            "changed_field": "case_decisions[COV-7204].next_local_action",
            "before_sha256": before, "after_sha256": after,
        }
        (workspace / "conflict_probe.json").write_text(json.dumps(conflict_probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        handoff = """# Continuation-coverage notice recovery handoff

The local run `CONT-REC-2026-08-14` first restored both open before-image journal entries. That restored `COV-7203` from the crash-only retry state to its returned state and removed the partial queue insert. The stale checkpoint was treated as a comparison aid, not delivery truth. All eligibility events were replayed by `source_sequence`; verified provider receipts outranked callback timeouts.

`COV-7201` needs a corrected version-2 local notice because the verified version-3 beneficiary snapshot adds `P-7201-S`. `COV-7202` is preserved: receipt `RCPT-7202-D` proves delivery and prevents a duplicate notice despite the earlier timeout. `COV-7203` has a verified returned receipt and a later HR-verified address version 2, so only a version-2 reissue package was staged. `COV-7204` has an accepted-only provider observation but no delivered or returned terminal receipt; it is held for receipt investigation, not guessed delivered and not resent. `COV-7205` is already beyond notice delivery with a delivered receipt and election event, so that post-notice state is preserved. `COV-7206` is held for an identity conflict because the address event identifies a different employee. `COV-7207` was unsent beyond the 44-day scenario deadline and is staged for compliance review rather than backdated.

Four reviewer-only items were staged: corrected beneficiary notice, verified-address reissue, provider-receipt investigation, and deadline compliance review. The manifest binds the normalized semantic plan, recovered SQLite state, immutable-source checkpoint, and local bundle hashes. Independent verification passed, and reordered arrays plus equivalent `#case`/`#cases` and `#event`/`#event_id` locators replayed as an idempotent no-op. The conflict probe changed the `COV-7204` action and was rejected non-zero with byte-identical database, bundle, manifest, and receipt hashes.

No notice was sent, no provider was contacted, no enrollment or benefit coverage was started, stopped, terminated, or changed, and every staged action remains unexecuted pending human review.
"""
        (workspace / "continuance_handoff.md").write_text(handoff, encoding="utf-8")

        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        REFERENCE.mkdir(parents=True)
        for name in ("recovery_plan.json", "equivalent_recovery_plan.json", "conflict_probe_plan.json", "conflict_probe.json", ".continuance_preview.json", "continuance_handoff.md"):
            shutil.copy2(workspace / name, REFERENCE / name)
        for directory, names in {
            "state": ["continuance.db", "verification.json", "staging_receipt.json", "replay_report.json"],
            "staging": ["notice_review_queue.json", "queue_manifest.json"],
        }.items():
            (REFERENCE / directory).mkdir()
            for name in names:
                shutil.copy2(workspace / directory / name, REFERENCE / directory / name)


if __name__ == "__main__":
    main()
