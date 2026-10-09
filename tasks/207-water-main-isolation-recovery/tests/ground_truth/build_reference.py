from __future__ import annotations

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
TRUTH = TASK / "tests/ground_truth/ground_truth.json"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def controller(path: Path):
    spec = importlib.util.spec_from_file_location("water_fixture_controller", path / "waterctl.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_plan(module) -> dict[str, object]:
    """Hidden fixture builder; never copied into the agent workspace."""
    context = module._validation_context()
    policy = context["policy"]
    selected = context["selected"]
    selected_members = context["selected_members"]
    valves = context["valves"]
    observed = context["observed"]
    decisions = []
    for valve_id in sorted(valves):
        valve = valves[valve_id]
        if valve["maintenance_locked"]:
            disposition, reason, next_action = "preserve_maintenance_lock", "maintenance_lock", "coordinate_lock_owner"
        elif observed[valve_id] != "operable":
            disposition, reason, next_action = "preserve_unavailable", "unavailable", "field_assessment_required"
        elif valve["critical_feed"]:
            disposition, reason, next_action = "preserve_critical_feed", "critical_feed", "critical_service_review"
        elif valve_id in selected_members:
            disposition, reason, next_action = "stage_close", "selected_boundary", "field_authorization_required"
        else:
            disposition, reason, next_action = "preserve_open", "outside_boundary", "none"
        desired = "closed" if disposition == "stage_close" else valve["physical_position"]
        refs = [f"state/network.db#valves:{valve_id}", "policy/isolation_policy.json#reason_precedence"]
        if valve_id in selected_members:
            refs.extend([f"state/network.db#boundaries:{selected}", f"state/network.db#boundary_valves:{selected}/{valve_id}"])
        if valve_id in context["accepted_observations"]:
            delivery_id = next(key for key, row in context["delivery_rules"].items() if row["valve_id"] == valve_id and row["disposition"] == "apply_observation")
            refs.append(f"evidence/telemetry_events.jsonl#{delivery_id}")
        decisions.append({
            "valve_id": valve_id, "observed_operability": observed[valve_id],
            "desired_position": desired, "disposition": disposition,
            "reason_codes": [reason],
            "impacted_zone_ids": context["selected_zones"] if valve_id in selected_members else [],
            "local_mutations": [f"local_desired_position={desired}", f"local_disposition={disposition}"],
            "next_local_action": next_action, "evidence_refs": refs,
        })
    boundary = context["boundaries"][selected]
    return {
        "schema_version": 1, "recovery_id": policy["recovery_id"],
        "source_checkpoint": context["checkpoint"], "work_order_id": policy["work_order_id"],
        "selected_boundary_id": selected, "valve_decisions": decisions,
        "delivery_dispositions": list(context["delivery_rules"].values()),
        "impact_summary": {
            "selected_boundary_id": selected,
            "affected_connections": boundary["affected_connections"],
            "critical_service_outages": boundary["critical_service_outages"],
            "valves_to_close": sorted(selected_members),
            "unavailable_valves": sorted(key for key, value in observed.items() if value != "operable"),
            "protected_valves": sorted(key for key, value in valves.items() if value["maintenance_locked"] or value["critical_feed"]),
            "quarantined_deliveries": sorted(key for key, row in context["delivery_rules"].items() if row["disposition"].startswith("quarantine_")),
        },
        "external_actions_executed": False,
    }


def handoff() -> str:
    return """# Offline water-main isolation recovery handoff

## Authority and telemetry intake

Distribution control used only the protected network database, the source manifest, the local telemetry delivery file, and the published isolation policy. Delivery order was not treated as business order. D-002 and D-004 are exact redeliveries and were ignored. D-051 and D-052 were both quarantined because EV-COLLIDE-04 reused one event identity with conflicting bodies. D-061 and D-062 were both quarantined because different identities occupied V-06 source sequence 8. D-091 names unknown V-99 and was ignored. D-011 is not newer than V-01's high-water mark, so it was ignored as stale. D-071 could not alter maintenance-locked V-05. Current accepted observations leave V-03 operable and establish V-02 as stuck open.

## Boundary adjudication

- B-A affects 120 connections and no critical service, but it is inadmissible because required V-02 is stuck open.
- B-B affects 145 connections across Z-EAST and Z-NORTH, has no critical-service outage, and both V-03 and V-04 are operable and unlocked. It is admissible.
- B-C would affect 80 connections but crosses the maintenance lock on V-05, so it is inadmissible.
- B-D would affect only 60 connections, but it would interrupt the Z-HOSPITAL critical feed through V-07, so it is inadmissible.

B-B is therefore the admissible minimum-impact boundary. The local projection stages V-03 and V-04 as desired closed while preserving their physical positions. V-02 remains open and unavailable pending field assessment; V-05 remains under its maintenance lock; V-07 remains an open critical feed; and V-01 and V-06 remain open outside the selected boundary.

## Recovery and closure

The open J-INT-V04 journal restored V-04's before-image and removed the interrupted projection before one atomic seven-valve projection committed. Verification reopened SQLite and reconciled the recovery identity, protected source checkpoint, normalized plan hash, journal closure, seven projections, and unchanged physical valve positions. The staged isolation-review packet and this handoff are bound by SHA-256 values in the packet manifest. Reordering valve rows, delivery rows, set-valued fields, or JSON formatting is a semantic replay no-op and leaves the database byte-identical.

This is an offline synthetic planning exercise only. No physical valve was operated, no water service was interrupted, and no crew, customer, hospital, regulator, approval workflow, notification channel, or external system was contacted, dispatched, submitted to, or changed.
"""


def main() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hb143-reference-") as temporary:
        run = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, run)
        module = controller(run)
        plan = reference_plan(module)
        (run / "isolation_recovery_plan.json").write_bytes(canonical(plan))
        (run / "isolation_handoff.md").write_text(handoff(), encoding="utf-8")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", "waterctl.py", command, "isolation_recovery_plan.json"],
                cwd=run, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
        for relative in (
            "isolation_recovery_plan.json", ".isolation_preview.json", "isolation_handoff.md",
            "state/network.db", "state/recovery_receipt.json", "state/verification.json",
            "state/replay_report.json", "staging/isolation_review_packet.json",
            "staging/packet_manifest.json",
        ):
            source = run / relative
            target = REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        with sqlite3.connect(run / "state/network.db") as con:
            columns = ("valve_id", "physical_position", "base_operability", "maintenance_locked", "critical_feed", "high_water_sequence")
            protected = [dict(zip(columns, row, strict=True)) for row in con.execute(f"SELECT {','.join(columns)} FROM valves ORDER BY valve_id").fetchall()]
        TRUTH.write_bytes(canonical({
            "plan": plan,
            "protected_valves": protected,
            "interrupted_recovery_id": "WIR-INTERRUPTED-00",
        }))


if __name__ == "__main__":
    main()
