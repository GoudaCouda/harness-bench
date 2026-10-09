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


def signed(payload: dict[str, object], key_id: str, material: str) -> dict[str, object]:
    return {
        **payload,
        "key_id": key_id,
        "signature": digest(canonical(payload) + material.encode()),
    }


def main() -> None:
    policy = {
        "schema_version": 1,
        "recovery_id": "MCR-20260815-01",
        "as_of_utc": "2026-08-15T18:00:00Z",
        "guard_band_rule": "accept_when_abs_error_plus_expanded_uncertainty_lte_tolerance",
        "reference_rule": "all_chain_standards_valid_at_calibration_unless_recall_affected_from_overrides",
        "event_rule": "deduplicate_event_id_then_apply_sequence; latest_measurement_correction_wins",
        "evidence_rule": "signed_event_and_matching_attachment_sha256_required",
        "traceability_status_values": ["traceable", "untraceable", "evidence_unavailable"],
        "measurement_decision_values": ["accept", "reject", "not_evaluable"],
        "certificate_action_values": ["affirm_valid", "revoke_reference_recall", "revoke_out_of_tolerance", "hold_evidence_review"],
        "asset_action_values": ["release_local_status", "quarantine_local_status", "hold_local_status"],
        "stage_boundary": "offline_quality_review_only",
        "plan_schema": {
            "top_level_fields": ["schema_version", "recovery_id", "source_checkpoint", "decisions", "external_actions_executed"],
            "decision_fields": ["job_id", "asset_id", "certificate_id", "authoritative_result_id", "reference_chain", "traceability_status", "error_abs", "expanded_uncertainty", "guard_band_margin", "measurement_decision", "certificate_action", "asset_action", "downstream_scope", "local_mutations", "evidence_refs"],
            "set_fields": ["reference_chain", "downstream_scope", "local_mutations", "evidence_refs"],
        },
    }
    write_json(WORKSPACE / "policy/metrology_policy.json", policy)

    trust = {
        "schema_version": 1,
        "key_id": "lab-qms-events-2026",
        "verification_material": "synthetic-offline-metrology-verifier-137-v1",
    }
    write_json(WORKSPACE / "evidence/event_trust.json", trust)
    standards = {
        "schema_version": 1,
        "standards": [
            {"standard_id": "STD-ROOT-A", "parent_standard_id": None, "valid_from_utc": "2025-01-01T00:00:00Z", "valid_to_utc": "2027-01-01T00:00:00Z", "recorded_status": "valid"},
            {"standard_id": "STD-P9", "parent_standard_id": "STD-ROOT-A", "valid_from_utc": "2026-01-01T00:00:00Z", "valid_to_utc": "2026-12-31T23:59:59Z", "recorded_status": "valid"},
            {"standard_id": "STD-T4", "parent_standard_id": "STD-ROOT-A", "valid_from_utc": "2026-01-01T00:00:00Z", "valid_to_utc": "2026-12-31T23:59:59Z", "recorded_status": "valid"},
            {"standard_id": "STD-M2", "parent_standard_id": "STD-ROOT-A", "valid_from_utc": "2025-08-01T00:00:00Z", "valid_to_utc": "2026-08-01T00:00:00Z", "recorded_status": "valid"},
            {"standard_id": "STD-H7", "parent_standard_id": "STD-ROOT-A", "valid_from_utc": "2026-01-01T00:00:00Z", "valid_to_utc": "2026-12-31T23:59:59Z", "recorded_status": "valid"},
            {"standard_id": "STD-C3", "parent_standard_id": "STD-ROOT-A", "valid_from_utc": "2026-01-01T00:00:00Z", "valid_to_utc": "2026-12-31T23:59:59Z", "recorded_status": "valid"},
        ],
    }
    write_json(WORKSPACE / "evidence/reference_standards.json", standards)

    results = {
        "RES-501": {"job_id": "JOB-501", "error": "0.20", "expanded_uncertainty": "0.20", "unit": "bar"},
        "RES-502": {"job_id": "JOB-502", "error": "-0.60", "expanded_uncertainty": "0.40", "unit": "N.m"},
        "RES-503": {"job_id": "JOB-503", "error": "0.25", "expanded_uncertainty": "0.20", "unit": "g"},
        "RES-504": {"job_id": "JOB-504", "error": "0.10", "expanded_uncertainty": "0.15", "unit": "%RH"},
        "RES-505-A": {"job_id": "JOB-505", "error": "0.10", "expanded_uncertainty": "0.10", "unit": "mm"},
        "RES-505-C": {"job_id": "JOB-505", "error": "0.45", "expanded_uncertainty": "0.10", "unit": "mm"},
        "RES-506": {"job_id": "JOB-506", "error": "0.05", "expanded_uncertainty": "0.10", "unit": "V"},
    }
    result_dir = WORKSPACE / "evidence/results"
    result_dir.mkdir(parents=True, exist_ok=True)
    for result_id, value in results.items():
        write_json(result_dir / f"{result_id}.json", value)

    def measurement(event_id: str, sequence: int, job_id: str, result_id: str, chain: list[str], kind: str = "measurement_recorded", *, bad_hash: bool = False) -> dict[str, object]:
        payload = {
            "event_id": event_id,
            "sequence": sequence,
            "kind": kind,
            "job_id": job_id,
            "result_id": result_id,
            "reference_chain": chain,
            "attachment": f"evidence/results/{result_id}.json",
            "attachment_sha256": "0" * 64 if bad_hash else digest((result_dir / f"{result_id}.json").read_bytes()),
        }
        return signed(payload, trust["key_id"], trust["verification_material"])

    recall_payload = {
        "event_id": "EV-RECALL-P9",
        "sequence": 205,
        "kind": "standard_recalled",
        "standard_id": "STD-P9",
        "affected_from_utc": "2026-07-01T00:00:00Z",
        "reason": "reference_drift_outside_limit",
    }
    c3_payload = {
        "event_id": "EV-RECALL-C3",
        "sequence": 208,
        "kind": "standard_recalled",
        "standard_id": "STD-C3",
        "affected_from_utc": "2026-07-12T00:00:00Z",
        "reason": "parent_link_invalidated",
    }
    events = [
        measurement("EV-M503", 103, "JOB-503", "RES-503", ["STD-M2", "STD-ROOT-A"]),
        signed(recall_payload, trust["key_id"], trust["verification_material"]),
        measurement("EV-M501", 101, "JOB-501", "RES-501", ["STD-P9", "STD-ROOT-A"]),
        measurement("EV-M505-C", 207, "JOB-505", "RES-505-C", ["STD-T4", "STD-ROOT-A"], "measurement_corrected"),
        measurement("EV-M502", 102, "JOB-502", "RES-502", ["STD-T4", "STD-ROOT-A"]),
        measurement("EV-M504", 104, "JOB-504", "RES-504", ["STD-H7", "STD-ROOT-A"], bad_hash=True),
        measurement("EV-M505-A", 105, "JOB-505", "RES-505-A", ["STD-T4", "STD-ROOT-A"]),
        signed(c3_payload, trust["key_id"], trust["verification_material"]),
        measurement("EV-M506", 106, "JOB-506", "RES-506", ["STD-C3", "STD-ROOT-A"]),
        measurement("EV-M505-C", 207, "JOB-505", "RES-505-C", ["STD-T4", "STD-ROOT-A"], "measurement_corrected"),
    ]
    event_path = WORKSPACE / "evidence/metrology_events.jsonl"
    event_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")

    db_path = WORKSPACE / "state/calibration.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    jobs = [
        ("JOB-501", "PRESSURE-P17", "CERT-501", "2026-07-10T14:00:00Z", "0.50", "issued", "released", 4),
        ("JOB-502", "TORQUE-T08", "CERT-502", "2026-07-11T10:00:00Z", "1.00", "issued", "released", 7),
        ("JOB-503", "MASS-M03", "CERT-503", "2026-07-20T09:00:00Z", "0.50", "issued", "released", 3),
        ("JOB-504", "HUMIDITY-H04", "CERT-504", "2026-07-22T16:00:00Z", "0.50", "issued", "released", 5),
        ("JOB-505", "CALIPER-C05", "CERT-505", "2026-07-13T11:00:00Z", "0.50", "issued", "released", 8),
        ("JOB-506", "VOLTAGE-V06", "CERT-506", "2026-07-15T13:00:00Z", "0.30", "issued", "released", 6),
    ]
    uses = [
        ("USE-501-A", "JOB-501", "WO-8801", "2026-07-11T08:00:00Z", "accepted"),
        ("USE-501-B", "JOB-501", "WO-8802", "2026-07-18T08:00:00Z", "accepted"),
        ("USE-502-A", "JOB-502", "WO-8810", "2026-07-12T08:00:00Z", "accepted"),
        ("USE-503-A", "JOB-503", "WO-8820", "2026-07-21T08:00:00Z", "accepted"),
        ("USE-505-A", "JOB-505", "WO-8830", "2026-07-14T08:00:00Z", "accepted"),
        ("USE-506-A", "JOB-506", "WO-8840", "2026-07-16T08:00:00Z", "accepted"),
        ("USE-506-OLD", "JOB-506", "WO-8700", "2026-07-01T08:00:00Z", "accepted"),
    ]
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE calibration_jobs(
              job_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL UNIQUE,
              certificate_id TEXT NOT NULL UNIQUE, calibrated_at_utc TEXT NOT NULL,
              tolerance TEXT NOT NULL, certificate_status TEXT NOT NULL,
              asset_status TEXT NOT NULL, version INTEGER NOT NULL
            );
            CREATE TABLE downstream_uses(
              use_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, work_order_id TEXT NOT NULL,
              occurred_at_utc TEXT NOT NULL, review_status TEXT NOT NULL
            );
            CREATE TABLE control_assessments(
              job_id TEXT PRIMARY KEY, result_id TEXT, traceability_status TEXT NOT NULL,
              measurement_decision TEXT NOT NULL, guard_band_margin TEXT,
              semantic_plan_digest TEXT NOT NULL
            );
            CREATE TABLE recall_actions(
              recovery_id TEXT NOT NULL, use_id TEXT NOT NULL,
              action TEXT NOT NULL, PRIMARY KEY(recovery_id,use_id)
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY, status TEXT NOT NULL,
              source_checkpoint TEXT NOT NULL, semantic_plan_digest TEXT NOT NULL,
              semantic_db_digest TEXT NOT NULL, final_revision INTEGER NOT NULL,
              external_actions_executed INTEGER NOT NULL CHECK(external_actions_executed IN (0,1))
            );
            CREATE TABLE recovery_journal(
              journal_id INTEGER PRIMARY KEY AUTOINCREMENT, recovery_id TEXT NOT NULL,
              entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
              before_json TEXT NOT NULL, restored INTEGER NOT NULL CHECK(restored IN (0,1))
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO calibration_jobs VALUES (?,?,?,?,?,?,?,?)", jobs)
        connection.executemany("INSERT INTO downstream_uses VALUES (?,?,?,?,?)", uses)
        before = {
            "job_id": "JOB-501", "asset_id": "PRESSURE-P17", "certificate_id": "CERT-501",
            "calibrated_at_utc": "2026-07-10T14:00:00Z", "tolerance": "0.50",
            "certificate_status": "issued", "asset_status": "released", "version": 4,
        }
        connection.execute("UPDATE calibration_jobs SET certificate_status='revoked_reference_recall',asset_status='quarantine_local',version=5 WHERE job_id='JOB-501'")
        connection.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?,?,?)", ("MCR-INTERRUPTED-00", "interrupted", "old-checkpoint", "old-plan", "", 0, 0))
        connection.execute("INSERT INTO recovery_journal(recovery_id,entity_type,entity_id,before_json,restored) VALUES (?,?,?,?,0)", ("MCR-INTERRUPTED-00", "calibration_jobs", "JOB-501", canonical(before).decode().strip()))
        connection.executemany("INSERT INTO system_state VALUES (?,?)", [("source_revision", "73"), ("current_revision", "73"), ("stage_state", "interrupted_local_control")])
        connection.commit()

    source_files = [
        "policy/metrology_policy.json",
        "evidence/event_trust.json",
        "evidence/reference_standards.json",
        "evidence/metrology_events.jsonl",
        *[f"evidence/results/{result_id}.json" for result_id in sorted(results)],
    ]
    manifest = {"schema_version": 1, "files": {name: digest((WORKSPACE / name).read_bytes()) for name in source_files}}
    write_json(WORKSPACE / "policy/source_manifest.json", manifest)


if __name__ == "__main__":
    main()
