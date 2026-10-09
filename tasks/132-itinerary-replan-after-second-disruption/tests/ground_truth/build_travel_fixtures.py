from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    policy = {
        "schema_version": 1,
        "recovery_id": "TRIP-20261015-SECOND-01",
        "trip_id": "TRIP-4187",
        "inventory_as_of": "2026-10-14T18:10:00-04:00",
        "destination_timezone": "America/Vancouver",
        "objective_order": ["fewest_reviewed_air_legs_changed", "lowest_incremental_cost_cad", "option_id"],
        "minimum_connection_minutes": {"same_airport": 75, "airport_change": 180},
        "arrival_curfew": "2026-10-15T20:00:00-07:00",
        "hotel_checkin_deadline": "2026-10-15T22:00:00-07:00",
        "event_arrival_deadline": "2026-10-16T08:30:00-07:00",
        "required_rest_minutes_before_event": 540,
        "traveler_constraints": {
            "accessibility_code": "WCHR",
            "checked_bags": 1,
            "authorized_transit_countries": ["CA", "US"],
            "airport_change_allowed": False,
        },
        "stage_boundary": "local_proposal_holds_and_requests_only",
        "plan_schema": {
            "top_level_fields": ["schema_version", "recovery_id", "source_checkpoint", "inventory_snapshot_id", "selected_option_id", "option_assessments", "applied_event_ids", "ignored_duplicate_delivery_ids", "object_decisions", "external_actions_executed"],
            "assessment_fields": ["option_id", "feasible", "reviewed_air_legs_changed", "incremental_cost_cad", "violations", "evidence_refs"],
            "decision_fields": ["object_id", "prior_state", "final_state", "action", "selected_inventory_object", "local_stage_kind", "evidence_refs", "external_action"],
        },
    }
    write_json(WORKSPACE / "policy/replan_policy.json", policy)

    trust = {
        "schema_version": 1,
        "key_id": "travel-inventory-key-2026q4",
        "verification_material": "synthetic-offline-verifier-132-v1",
    }
    write_json(WORKSPACE / "evidence/inventory_trust.json", trust)
    inventory_payload = {
        "schema_version": 1,
        "snapshot_id": "INV-20261014T221000Z",
        "etag": "inventory-v37",
        "valid_until": "2026-10-14T19:00:00-04:00",
        "options": [
            {
                "option_id": "O-D", "incremental_cost_cad": 110, "transit_countries": ["US", "CA"], "accessibility_codes": ["WCHR"], "checked_bag_mode": "through_checked",
                "segments": [
                    {"segment_id": "LEG-1", "mode": "air", "from": "BOS", "to": "JFK", "depart": "2026-10-15T08:00:00-04:00", "arrive": "2026-10-15T09:15:00-04:00", "reviewed_segment": True},
                    {"segment_id": "OD-2", "mode": "air", "from": "JFK", "to": "YVR", "depart": "2026-10-15T10:10:00-04:00", "arrive": "2026-10-15T13:25:00-07:00", "reviewed_segment": False},
                ],
            },
            {
                "option_id": "O-E", "incremental_cost_cad": 135, "transit_countries": ["US", "CA"], "accessibility_codes": ["WCHR"], "checked_bag_mode": "through_checked",
                "segments": [
                    {"segment_id": "LEG-1", "mode": "air", "from": "BOS", "to": "JFK", "depart": "2026-10-15T08:00:00-04:00", "arrive": "2026-10-15T09:15:00-04:00", "reviewed_segment": True},
                    {"segment_id": "OE-2", "mode": "air", "from": "JFK", "to": "SEA", "depart": "2026-10-15T11:20:00-04:00", "arrive": "2026-10-15T14:15:00-07:00", "reviewed_segment": False},
                    {"segment_id": "OE-3", "mode": "rail", "from": "SEA", "to": "Vancouver Pacific Central", "depart": "2026-10-15T17:45:00-07:00", "arrive": "2026-10-15T21:45:00-07:00", "reviewed_segment": False},
                ],
            },
            {
                "option_id": "O-F", "incremental_cost_cad": 260, "transit_countries": ["US", "CA"], "accessibility_codes": ["WCHR"], "checked_bag_mode": "through_checked",
                "segments": [
                    {"segment_id": "LEG-1", "mode": "air", "from": "BOS", "to": "JFK", "depart": "2026-10-15T08:00:00-04:00", "arrive": "2026-10-15T09:15:00-04:00", "reviewed_segment": True},
                    {"segment_id": "OF-2", "mode": "air", "from": "JFK", "to": "YVR", "depart": "2026-10-15T11:35:00-04:00", "arrive": "2026-10-15T16:05:00-07:00", "reviewed_segment": False},
                ],
            },
            {
                "option_id": "O-G", "incremental_cost_cad": 90, "transit_countries": ["US", "GB", "CA"], "accessibility_codes": ["WCHR"], "checked_bag_mode": "recheck_required",
                "segments": [
                    {"segment_id": "LEG-1", "mode": "air", "from": "BOS", "to": "JFK", "depart": "2026-10-15T08:00:00-04:00", "arrive": "2026-10-15T09:15:00-04:00", "reviewed_segment": True},
                    {"segment_id": "OG-2", "mode": "air", "from": "JFK", "to": "LHR", "depart": "2026-10-15T11:00:00-04:00", "arrive": "2026-10-15T22:50:00+01:00", "reviewed_segment": False},
                    {"segment_id": "OG-3", "mode": "air", "from": "LHR", "to": "YVR", "depart": "2026-10-16T09:30:00+01:00", "arrive": "2026-10-16T11:15:00-07:00", "reviewed_segment": False},
                ],
            },
            {
                "option_id": "O-H", "incremental_cost_cad": 180, "transit_countries": ["US", "CA"], "accessibility_codes": ["WCHR"], "checked_bag_mode": "through_checked",
                "segments": [
                    {"segment_id": "OH-1", "mode": "air", "from": "BOS", "to": "ORD", "depart": "2026-10-15T07:25:00-04:00", "arrive": "2026-10-15T09:15:00-05:00", "reviewed_segment": False},
                    {"segment_id": "OH-2", "mode": "air", "from": "ORD", "to": "YVR", "depart": "2026-10-15T11:10:00-05:00", "arrive": "2026-10-15T15:20:00-07:00", "reviewed_segment": False},
                ],
            },
            {
                "option_id": "O-I", "incremental_cost_cad": 310, "transit_countries": ["US", "CA"], "accessibility_codes": ["WCHR"], "checked_bag_mode": "through_checked",
                "segments": [
                    {"segment_id": "LEG-1", "mode": "air", "from": "BOS", "to": "JFK", "depart": "2026-10-15T08:00:00-04:00", "arrive": "2026-10-15T09:15:00-04:00", "reviewed_segment": True},
                    {"segment_id": "OI-2", "mode": "air", "from": "JFK", "to": "YVR", "depart": "2026-10-15T12:05:00-04:00", "arrive": "2026-10-15T16:30:00-07:00", "reviewed_segment": False},
                ],
            },
        ],
        "dependent_inventory": {
            "shuttle_slots": [
                {"slot_id": "SH-1700", "airport": "YVR", "pickup": "2026-10-15T17:00:00-07:00", "latest_flight_arrival": "2026-10-15T16:20:00-07:00", "accessibility_codes": ["WCHR"]},
                {"slot_id": "SH-1900", "airport": "YVR", "pickup": "2026-10-15T19:00:00-07:00", "latest_flight_arrival": "2026-10-15T18:20:00-07:00", "accessibility_codes": []},
            ],
            "station_to_hotel_minutes": 40,
        },
    }
    inventory = {**inventory_payload, "key_id": trust["key_id"]}
    inventory["signature"] = digest(canonical(inventory_payload) + trust["verification_material"].encode())
    write_json(WORKSPACE / "evidence/inventory_snapshot.json", inventory)

    deliveries = [
        {"delivery_id": "DLV-04", "event_id": "EVT-503", "sequence": 503, "kind": "hotel_late_checkin_confirmed", "object_id": "HOTEL", "value": "2026-10-15T22:00:00-07:00"},
        {"delivery_id": "DLV-01", "event_id": "EVT-501", "sequence": 501, "kind": "segment_cancelled", "object_id": "AIR-2", "value": "LEG-2"},
        {"delivery_id": "DLV-03", "event_id": "EVT-502", "sequence": 502, "kind": "shuttle_slot_withdrawn", "object_id": "SHUTTLE", "value": "SH-OLD"},
        {"delivery_id": "DLV-02", "event_id": "EVT-501", "sequence": 501, "kind": "segment_cancelled", "object_id": "AIR-2", "value": "LEG-2"},
    ]
    events_path = WORKSPACE / "evidence/disruption_events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in deliveries), encoding="utf-8")

    db_path = WORKSPACE / "state/travel.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    objects = [
        ("AIR-1", "air", "reviewed_confirmed:LEG-1", "LEG-1", 7),
        ("AIR-2", "air", "interrupted_candidate:OD-2", "OD-2", 8),
        ("RAIL", "rail", "inactive_fallback", "none", 3),
        ("HOTEL", "hotel", "reviewed_confirmed:H-VAN-22", "H-VAN-22", 4),
        ("SHUTTLE", "shuttle", "reviewed_hold:SH-OLD", "SH-OLD", 6),
        ("CAR", "car", "reviewed_not_needed", "none", 2),
        ("EVENT", "event", "reviewed_confirmed:EV-VAN-0915", "EV-VAN-0915", 5),
        ("REFUND", "refund", "not_staged", "none", 1),
    ]
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE itinerary_objects(
              object_id TEXT PRIMARY KEY, object_type TEXT NOT NULL,
              state TEXT NOT NULL, inventory_object TEXT NOT NULL, version INTEGER NOT NULL
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY, status TEXT NOT NULL,
              source_checkpoint TEXT NOT NULL, semantic_plan_digest TEXT NOT NULL,
              semantic_db_digest TEXT NOT NULL, final_revision INTEGER NOT NULL,
              external_actions_executed INTEGER NOT NULL CHECK(external_actions_executed IN (0,1))
            );
            CREATE TABLE recovery_journal(
              journal_id INTEGER PRIMARY KEY AUTOINCREMENT, recovery_id TEXT NOT NULL,
              object_id TEXT NOT NULL, before_json TEXT NOT NULL, restored INTEGER NOT NULL CHECK(restored IN (0,1))
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO itinerary_objects VALUES (?,?,?,?,?)", objects)
        before_air2 = {"object_id": "AIR-2", "object_type": "air", "state": "reviewed_confirmed:LEG-2", "inventory_object": "LEG-2", "version": 7}
        connection.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?,?,?)", ("TRIP-20261015-FIRST-INTERRUPTED", "interrupted", "old-checkpoint", "old-plan", "", 0, 0))
        connection.execute("INSERT INTO recovery_journal(recovery_id,object_id,before_json,restored) VALUES (?,?,?,0)", ("TRIP-20261015-FIRST-INTERRUPTED", "AIR-2", canonical(before_air2).decode().strip()))
        connection.executemany("INSERT INTO system_state VALUES (?,?)", [("source_revision", "41"), ("current_revision", "41"), ("stage_state", "interrupted_local_apply"), ("prior_reviewed_option", "O-B")])
        connection.commit()

    manifest_files = [
        "policy/replan_policy.json",
        "evidence/inventory_trust.json",
        "evidence/inventory_snapshot.json",
        "evidence/disruption_events.jsonl",
    ]
    manifest = {"schema_version": 1, "files": {name: digest((WORKSPACE / name).read_bytes()) for name in manifest_files}}
    write_json(WORKSPACE / "policy/source_manifest.json", manifest)


if __name__ == "__main__":
    main()
