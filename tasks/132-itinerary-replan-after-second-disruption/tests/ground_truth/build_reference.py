from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sqlite3
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any


TASK = Path(__file__).resolve().parents[2]
SEED = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def _controller(workspace: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "travel_reference_controller", workspace / "tripctl.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load temporary controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reference_plan(module: ModuleType) -> dict[str, Any]:
    """Build hidden reference data from the interrupted seed, never in public code."""
    policy = module.load_json(module.ROOT / "policy/replan_policy.json")
    manifest, source_bundle_hash = module.source_bundle()
    inventory = module.verified_inventory()
    delivered, ignored = module.events()
    with sqlite3.connect(module.DB) as connection:
        baseline, source_revision = module.baseline(connection)
    assessments = [
        module.assess_option(option, policy, inventory)
        for option in inventory["options"]
    ]
    selected = min(
        (row for row in assessments if row["feasible"]),
        key=lambda row: (
            row["reviewed_air_legs_changed"],
            row["incremental_cost_cad"],
            row["option_id"],
        ),
    )["option_id"]
    checkpoint = module.digest(
        module.canonical(
            {
                "source_hashes": manifest["files"],
                "source_bundle_hash": source_bundle_hash,
                "source_revision": source_revision,
                "baseline_objects": baseline,
            }
        )
    )
    source_by_id = {row["object_id"]: row for row in baseline}
    decision_values = {
        "AIR-1": (
            "reviewed_confirmed:LEG-1", "preserve", "LEG-1", "none",
            ["evidence/inventory_snapshot.json#O-F", "state/travel.db#AIR-1"],
        ),
        "AIR-2": (
            "local_proposal_hold:OF-2", "replace_disrupted_leg", "OF-2", "hold_request",
            ["evidence/disruption_events.jsonl#EVT-501", "evidence/inventory_snapshot.json#O-F"],
        ),
        "CAR": (
            "reviewed_not_needed", "preserve", "none", "none",
            ["policy/replan_policy.json#stage_boundary", "state/travel.db#CAR"],
        ),
        "EVENT": (
            "reviewed_confirmed:EV-VAN-0915", "preserve", "EV-VAN-0915", "none",
            ["evidence/inventory_snapshot.json#O-F", "state/travel.db#EVENT"],
        ),
        "HOTEL": (
            "reviewed_confirmed:H-VAN-22", "preserve", "H-VAN-22", "none",
            ["evidence/disruption_events.jsonl#EVT-503", "state/travel.db#HOTEL"],
        ),
        "RAIL": (
            "inactive_fallback", "preserve", "none", "none",
            ["evidence/inventory_snapshot.json#O-F", "state/travel.db#RAIL"],
        ),
        "REFUND": (
            "local_request_staged:LEG-2", "stage_refund_request", "LEG-2", "request",
            ["evidence/disruption_events.jsonl#EVT-501", "policy/replan_policy.json#stage_boundary"],
        ),
        "SHUTTLE": (
            "local_proposal_hold:SH-1700", "replace_with_accessible_slot", "SH-1700", "hold_request",
            ["evidence/disruption_events.jsonl#EVT-502", "evidence/inventory_snapshot.json#SH-1700"],
        ),
    }
    decisions = []
    for object_id in sorted(source_by_id):
        final_state, action, inventory_object, stage_kind, refs = decision_values[object_id]
        decisions.append(
            {
                "object_id": object_id,
                "prior_state": source_by_id[object_id]["state"],
                "final_state": final_state,
                "action": action,
                "selected_inventory_object": inventory_object,
                "local_stage_kind": stage_kind,
                "evidence_refs": sorted(refs),
                "external_action": "none",
            }
        )
    return {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": checkpoint,
        "inventory_snapshot_id": inventory["snapshot_id"],
        "selected_option_id": selected,
        "option_assessments": assessments,
        "applied_event_ids": [row["event_id"] for row in delivered],
        "ignored_duplicate_delivery_ids": ignored,
        "object_decisions": decisions,
        "external_actions_executed": False,
    }


def _handoff() -> str:
    return """# Local itinerary recovery handoff

## Authority and event recovery

The valid signed inventory snapshot `INV-20261014T221000Z` (ETag
`inventory-v37`) was checked against the local trust material and remained valid
at the policy as-of time; its signature was verified. Delivery order was
normalized by sequence. `EVT-501`, `EVT-502`, and `EVT-503` were applied once;
repeated delivery `DLV-02` of `EVT-501` was ignored as a duplicate. The earlier
interrupted journal was recovered before this recovery was committed atomically.

## Option decision

O-F is the selected proposal. It preserves reviewed LEG-1 and replaces only the
cancelled LEG-2, meets the 75-minute connection rule, arrives at 16:05 PDT before
the curfew, supports WCHR and a through-checked bag, stays within US/Canada
transit authority, connects to accessible shuttle SH-1700, and leaves the hotel
and event windows intact. O-D misses the minimum connection. O-E arrives after
curfew and misses the dependent timing windows. O-G requires unauthorized GB
transit, a checked-bag recheck, and arrives the next day. O-I has no accessible
shuttle connection. O-H is feasible and CAD 180 versus O-F's CAD 260, but it
replaces both reviewed air legs and is cheaper; the published minimum-change
objective therefore dominates cost and correctly retains O-F.

## Minimal object delta and local stage

AIR-1, the inactive RAIL fallback, HOTEL H-VAN-22, CAR not-needed state, and
EVENT EV-VAN-0915 were preserved. AIR-2 is a local proposal hold for OF-2,
SHUTTLE is a local proposal hold for accessible SH-1700, and REFUND is only a
staged local request for cancelled LEG-2. The receipt contains two local hold
tokens and one local request token. The RFC 5545 itinerary is TENTATIVE.

Verification closed the source checkpoint, semantic plan, exact SQLite object
projection, event deduplication, objective, revision, and recovered journal.
Semantic replay left the database, receipt, and calendar byte-stable with one
committed recovery identity.

No booking, cancellation, refund submission, purchase, payment, or message was
executed. All holds, requests, and calendar entries remain offline proposals for
human review.
"""


def main() -> None:
    seed_before = _tree_hashes(SEED)
    with tempfile.TemporaryDirectory(prefix="hb132-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(SEED, workspace)
        module = _controller(workspace)
        plan_path = workspace / "replan_plan.json"
        module.write_json(plan_path, _reference_plan(module))
        module.preview(plan_path)
        module.apply(plan_path)
        module.verify(plan_path)
        module.stage(plan_path)
        module.replay(plan_path)
        (workspace / "replan_handoff.md").write_text(_handoff(), encoding="utf-8")
        for relative in (
            "replan_plan.json", ".trip_preview.json", "state/travel.db",
            "state/verification.json", "state/stage_receipt.json",
            "state/replay_report.json", "itinerary.ics", "replan_handoff.md",
        ):
            destination = REFERENCE / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / relative, destination)
    if _tree_hashes(SEED) != seed_before:
        raise RuntimeError("reference build mutated the pristine seed workspace")


if __name__ == "__main__":
    main()
