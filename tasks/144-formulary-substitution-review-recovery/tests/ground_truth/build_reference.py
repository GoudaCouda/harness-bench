from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any

TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
TRUTH = TASK / "tests/ground_truth/ground_truth.json"
POLICY = WORKSPACE / "policy/formulary_policy.json"
EVENTS = WORKSPACE / "evidence/benefit_events.jsonl"
DB = WORKSPACE / "state/formulary.db"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows(con: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cur = con.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cur.description]
    return [dict(zip(names, row, strict=True)) for row in cur.fetchall()]


def source_state(database: Path) -> dict[str, Any]:
    with sqlite3.connect(database) as con:
        prescriptions = {
            row["rx_id"]: row for row in rows(con, "prescriptions", "rx_id")
        }
        runs = {
            row["recovery_id"]: row for row in rows(con, "review_runs", "recovery_id")
        }
        for journal in rows(con, "recovery_journal", "journal_id"):
            if (
                runs.get(journal["recovery_id"], {}).get("status") == "interrupted"
                and not journal["restored"]
            ):
                restored = dict(prescriptions[journal["rx_id"]])
                restored.update(json.loads(journal["before_json"]))
                prescriptions[journal["rx_id"]] = restored
        return {
            "source_revision": int(
                con.execute(
                    "SELECT value FROM system_state WHERE key='source_revision'"
                ).fetchone()[0]
            ),
            "members": rows(con, "members", "member_id"),
            "products": rows(con, "products", "product_code"),
            "prescriptions": [prescriptions[key] for key in sorted(prescriptions)],
            "formulary_rules": rows(con, "formulary_rules", "rule_id"),
            "step_records": rows(con, "step_records", "member_id,step_code"),
            "authorization_register": rows(
                con, "authorization_register", "document_id"
            ),
        }


def event_status(
    index: int,
    events: list[dict[str, Any]],
    prescriptions: dict[str, dict[str, Any]],
    protected: set[str],
) -> str:
    row = events[index]
    group = [
        (
            i,
            digest(
                canonical(
                    {
                        key: value
                        for key, value in candidate.items()
                        if key != "delivery_id"
                    }
                )
            ),
        )
        for i, candidate in enumerate(events)
        if candidate["event_id"] == row["event_id"]
    ]
    if len({item[1] for item in group}) > 1:
        return "event_identity_collision_quarantined"
    if index != min(item[0] for item in group):
        return "duplicate_delivery_ignored"
    for position, other in enumerate(events):
        if (
            position != index
            and other["rx_id"] == row["rx_id"]
            and other["source_sequence"] == row["source_sequence"]
            and other["event_id"] != row["event_id"]
        ):
            peer = [
                (i, candidate)
                for i, candidate in enumerate(events)
                if candidate["event_id"] == other["event_id"]
            ]
            hashes = {
                digest(
                    canonical(
                        {
                            key: value
                            for key, value in candidate.items()
                            if key != "delivery_id"
                        }
                    )
                )
                for _, candidate in peer
            }
            if len(hashes) == 1 and position == min(item[0] for item in peer):
                return "sequence_conflict_quarantined"
    rx = prescriptions.get(row["rx_id"])
    if rx is None:
        return "unknown_prescription_ignored"
    return "protected_boundary_ignored" if rx["status"] in protected else "applied"


def derive(database: Path, root: Path) -> dict[str, Any]:
    state = source_state(database)
    policy = json.loads((root / "policy/formulary_policy.json").read_text())
    events = [
        json.loads(line)
        for line in (root / "evidence/benefit_events.jsonl").read_text().splitlines()
    ]
    members, products = (
        {row["member_id"]: row for row in state["members"]},
        {row["product_code"]: row for row in state["products"]},
    )
    prescriptions = {row["rx_id"]: row for row in state["prescriptions"]}
    steps = {(row["member_id"], row["step_code"]) for row in state["step_records"]}
    auth = {row["rx_id"]: row for row in state["authorization_register"]}
    event_rows = [
        {
            "delivery_id": row["delivery_id"],
            "event_id": row["event_id"],
            "rx_id": row["rx_id"],
            "source_sequence": row["source_sequence"],
            "disposition": event_status(
                i, events, prescriptions, set(policy["protected_statuses"])
            ),
        }
        for i, row in enumerate(events)
    ]
    payload = {
        "source_revision": state["source_revision"],
        "members": state["members"],
        "products": state["products"],
        "prescriptions": [
            {key: value for key, value in row.items() if not key.startswith("local_")}
            for row in state["prescriptions"]
        ],
        "formulary_rules": state["formulary_rules"],
        "step_records": state["step_records"],
        "authorization_register": state["authorization_register"],
        "policy_sha256": digest((root / "policy/formulary_policy.json").read_bytes()),
        "events_sha256": digest((root / "evidence/benefit_events.jsonl").read_bytes()),
    }
    checkpoint = "sha256:" + digest(canonical(payload))
    totals = {
        "active_prescriptions": 0,
        "ready_prescriptions": 0,
        "held_prescriptions": 0,
        "preserved_dispensed_prescriptions": 0,
        "preserved_cancelled_prescriptions": 0,
    }
    decisions = []
    for rx_id in sorted(prescriptions):
        rx, member = prescriptions[rx_id], members[prescriptions[rx_id]["member_id"]]
        eligible = [
            row
            for row in state["formulary_rules"]
            if row["plan_id"] == member["plan_id"]
            and row["product_code"] == rx["current_product_code"]
            and row["effective_from"] <= rx["prescribed_at"]
            and (
                row["effective_to"] is None or rx["prescribed_at"] < row["effective_to"]
            )
        ]
        eligible.sort(key=lambda row: (row["effective_from"], row["rule_id"]))
        rule = eligible[-1] if eligible else None
        target = (
            rx["current_product_code"] if rule is None else rule["target_product_code"]
        )
        effective = [] if rule is None else [rule["rule_id"]]
        refs = {
            f"state/formulary.db#prescriptions:{rx_id}",
            f"state/formulary.db#members:{rx['member_id']}",
            "policy/formulary_policy.json#hold_precedence",
        }
        invalid, allergy, blockers = [], [], []
        if rule:
            refs.add(f"state/formulary.db#formulary_rules:{rule['rule_id']}")
            allergy = sorted(
                set(json.loads(member["allergy_codes_json"]))
                & set(json.loads(products[target]["excipient_codes_json"]))
            )
            if rule["requires_pa"]:
                doc, valid = auth.get(rx_id), False
                if doc:
                    refs.add(f"{doc['local_path']}#{doc['document_id']}")
                    source = json.loads((root / doc["local_path"]).read_text())
                    valid = bool(
                        doc["signed"]
                        and digest((root / doc["local_path"]).read_bytes())
                        == doc["sha256"]
                        and source.get("kind") == "prior_authorization"
                        and source.get("rx_id") == rx_id
                        and source.get("approved") is True
                        and source.get("valid_through", "") > policy["as_of_utc"]
                    )
                if not valid:
                    invalid.append(
                        doc["document_id"]
                        if doc
                        else f"missing_prior_authorization:{rx_id}"
                    )
        else:
            blockers.append(f"missing_effective_rule:{rx_id}")
        if rx["status"] == "dispensed":
            disposition = final = "dispensed_boundary_preserved"
            target, action = rx["current_product_code"], "none"
            effective, invalid, allergy, blockers = [], [], [], []
            totals["preserved_dispensed_prescriptions"] += 1
        elif rx["status"] == "cancelled":
            disposition = final = "cancelled_boundary_preserved"
            target, action = rx["current_product_code"], "none"
            effective, invalid, allergy, blockers = [], [], [], []
            totals["preserved_cancelled_prescriptions"] += 1
        else:
            totals["active_prescriptions"] += 1
            if invalid:
                disposition = final = "hold_evidence_integrity"
                action, blockers = "route_prior_authorization_review", sorted(invalid)
            elif rx["daw_code"] == "1":
                disposition = final = "hold_prescriber_daw"
                action, blockers = (
                    "route_prescriber_daw_review",
                    ["prescriber_daw_code:1"],
                )
            elif allergy:
                disposition = final = "hold_allergy_conflict"
                action, blockers = (
                    "route_clinical_allergy_review",
                    [f"target_excipient_allergy:{code}" for code in allergy],
                )
            elif (
                rule
                and rule["required_step_code"]
                and (rx["member_id"], rule["required_step_code"]) not in steps
            ):
                disposition = final = "hold_step_therapy"
                action, blockers = (
                    "route_step_therapy_review",
                    [f"missing_step:{rule['required_step_code']}"],
                )
            elif rule and rx["channel"] != rule["required_channel"]:
                disposition = final = "hold_channel_restriction"
                action, blockers = (
                    "route_specialty_channel_review",
                    [f"required_channel:{rule['required_channel']}"],
                )
            elif blockers:
                disposition = final = "hold_formulary_authority"
                action = "route_prior_authorization_review"
            else:
                disposition = final = policy["ready_state"]
                action, blockers = "stage_local_formulary_review", []
            totals[
                "ready_prescriptions"
                if disposition == policy["ready_state"]
                else "held_prescriptions"
            ] += 1
        refs.update(
            f"evidence/benefit_events.jsonl#{row['event_id']}"
            for row in event_rows
            if row["rx_id"] == rx_id and row["disposition"] == "applied"
        )
        mutations = (
            ["upsert_rx_projection"]
            if action == "none"
            else [
                f"set_local_disposition:{disposition}",
                f"set_local_target_product_code:{target}",
                f"set_local_next_action:{action}",
                "upsert_rx_projection",
            ]
        )
        decisions.append(
            {
                "rx_id": rx_id,
                "member_id": rx["member_id"],
                "current_product_code": rx["current_product_code"],
                "target_product_code": target,
                "disposition": disposition,
                "final_local_state": final,
                "effective_rule_ids": sorted(effective),
                "invalid_document_ids": sorted(invalid),
                "allergy_conflict_codes": sorted(allergy),
                "blocking_reasons": sorted(blockers),
                "local_mutations": sorted(mutations),
                "next_local_action": action,
                "evidence_refs": sorted(refs),
            }
        )
    return {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": checkpoint,
        "rx_decisions": decisions,
        "event_dispositions": sorted(event_rows, key=lambda row: row["delivery_id"]),
        "totals": totals,
        "external_actions_executed": False,
    }


def handoff() -> str:
    return """# Offline formulary-substitution recovery handoff

## Intake authority

The local benefit-event stream was reconciled independently of delivery order. DL-002 is an exact redelivery and was ignored. DL-011 and DL-012 reused one event identity with different content and were quarantined. DL-021 and DL-022 occupied RX-204 source sequence 7 under different event identities and were quarantined. RX-999 was unknown. Late traffic for RX-206 and RX-207 did not cross their dispensed and cancelled boundaries.

## Prescription review

- RX-201 is ready for local formulary review: FR-CARD-NEW was effective at prescription time and directly names GN-CARD-20.
- RX-202 is held for prescriber DAW code 1; no substitution was inferred.
- RX-203 is held for the EXC-LACTOSE allergy conflict in the proposed GN-NEUR-10 target.
- RX-204 is held because STEP-DERM is missing. Its interrupted ready projection was not accepted.
- RX-205 is ready through FR-IMM-1 because PA-205 is signed, hash-valid, unexpired, and the specialty channel matches.
- RX-206 remains at the dispensed protected boundary, and RX-207 remains at the cancelled protected boundary.
- RX-208 uses FR-CARD-OLD, the rule effective when prescribed, rather than retroactively substituting the current rule.
- RX-209 is held because FR-IMM-1 requires the specialty channel while this record remains retail.

## Recovery and closure

The J-INT-204 before-image restored RX-204 before one atomic nine-prescription local projection committed. Verification reopened SQLite and reconciled the journal, stable recovery identity, protected source checkpoint, normalized semantic plan hash, projection rows, and immutable source facts. The local formulary-review packet and this handoff are bound by SHA-256 in the packet manifest. Reordering decisions, events, set-valued fields, or JSON formatting is a semantic replay no-op and leaves SQLite byte-identical.

This was an offline administrative review only. We did not substitute, prescribe, dispense, cancel, adjudicate, authorize, approve, deny, contact, notify, transmit, or submit anything, and we did not change a pharmacy, benefit, prescriber, member, or clinical system.
"""


def main() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hb144-ref-") as temporary:
        run = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, run)
        plan = derive(run / "state/formulary.db", run)
        (run / "formulary_recovery_plan.json").write_bytes(canonical(plan))
        (run / "formulary_handoff.md").write_text(handoff(), encoding="utf-8")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", "formularyctl.py", command, "formulary_recovery_plan.json"],
                cwd=run,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        artifacts = (
            "formulary_recovery_plan.json",
            ".formulary_preview.json",
            "formulary_handoff.md",
            "state/formulary.db",
            "state/recovery_receipt.json",
            "state/verification.json",
            "state/replay_report.json",
            "staging/formulary_review_packet.json",
            "staging/packet_manifest.json",
        )
        for relative in artifacts:
            source, target = run / relative, REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        with sqlite3.connect(run / "state/formulary.db") as con:
            columns = (
                "rx_id",
                "member_id",
                "current_product_code",
                "prescribed_at",
                "status",
                "daw_code",
                "channel",
            )
            cur = con.execute(
                f"SELECT {','.join(columns)} FROM prescriptions ORDER BY rx_id"
            )
            protected = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
        TRUTH.write_bytes(
            canonical(
                {
                    "plan": plan,
                    "protected_prescriptions": protected,
                    "interrupted_recovery_id": "FSR-INTERRUPTED-00",
                }
            )
        )


if __name__ == "__main__":
    main()
