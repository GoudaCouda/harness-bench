#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def signed_claim(
    claim_id: str, issuer: str, payload: dict[str, object], key: str
) -> dict[str, object]:
    payload_sha256 = digest(canonical(payload))
    return {
        "claim_id": claim_id,
        "issuer": issuer,
        "payload": payload,
        "payload_sha256": payload_sha256,
        "signature": digest(f"{key}:{payload_sha256}".encode()),
    }


def main() -> None:
    for path in (
        WORKSPACE / "policy",
        WORKSPACE / "evidence",
        WORKSPACE / "state",
        REFERENCE,
    ):
        path.mkdir(parents=True, exist_ok=True)

    policy = {
        "schema_version": 1,
        "employer_id": "EMP-NORTHSTAR-17",
        "recovery_id": "REC-OSHA-2026-0716-A",
        "fixed_clock_utc": "2026-07-16T16:00:00Z",
        "signature_scheme": "sha256(issuer_secret + ':' + canonical_payload_sha256)",
        "authority_registry": {
            "HOSP-A": {
                "active": True,
                "scopes": ["medical_outcome"],
                "verification_secret": "synthetic-hosp-a-key",
            },
            "CLINIC-B": {
                "active": True,
                "scopes": ["medical_outcome"],
                "verification_secret": "synthetic-clinic-b-key",
            },
            "CORONER-C": {
                "active": True,
                "scopes": ["fatality_outcome"],
                "verification_secret": "synthetic-coroner-c-key",
            },
            "TEMP-X": {
                "active": False,
                "scopes": [],
                "verification_secret": "expired-temp-x-key",
            },
        },
        "event_precedence": [
            "deduplicate event_id by first delivery_index",
            "reject another employer_id",
            "reject medical claims without an active issuer, permitted scope, matching payload digest, and valid signature",
            "within each case_id and stream, apply only the highest eligible sequence",
        ],
        "recordability": {
            "recordable_medical_categories": [
                "fatality",
                "inpatient_admission",
                "medical_treatment_beyond_first_aid",
            ],
            "unknown_rule": "pending_evidence when work-relatedness or an authoritative medical outcome is missing",
        },
        "osha_reporting": {
            "fatality_deadline_hours": 8,
            "fatality_must_occur_within_days_of_incident": 30,
            "inpatient_deadline_hours": 24,
            "inpatient_must_occur_within_hours_of_incident": 24,
            "deadline_anchor": "employer_known_at from the controlling signed outcome",
            "already_submitted_rule": "preserve a verified observed receipt and never enqueue a duplicate",
            "emergency_room_only_is_reportable": False,
        },
        "privacy": {
            "allowed_medical_fields": [
                "medical_category",
                "outcome_at",
                "employer_known_at",
            ],
            "forbidden_output_fields": [
                "diagnosis",
                "treatment_notes",
                "employee_name",
            ],
            "cause_rule": "Never propagate a claimed cause; retain unverified_not_propagated unless a separate authorized investigation finding exists.",
        },
        "vocabulary": {
            "recordability": ["recordable", "not_recordable", "pending_evidence"],
            "osha_reporting_path": [
                "preserve_observed_submission",
                "stage_osha_24h_report",
                "not_osha_reportable",
                "hold_pending_verified_outcome",
            ],
            "workers_comp_action": ["stage_notice_offline", "hold_pending_evidence"],
            "cause_status": ["unverified_not_propagated"],
            "event_disposition": [
                "duplicate_delivery_ignored",
                "employer_mismatch_ignored",
                "invalid_authority_quarantined",
                "superseded_by_newer_sequence",
                "applied_current",
            ],
        },
    }
    write_json(WORKSPACE / "policy/reporting_policy.json", policy)

    keys = {
        issuer: row["verification_secret"]
        for issuer, row in policy["authority_registry"].items()
    }
    claim_specs = [
        (
            "CLM-771-OLD",
            "HOSP-A",
            {
                "case_id": "CASE-771",
                "scope": "medical_outcome",
                "medical_category": "emergency_room_only",
                "outcome_at": "2026-07-14T23:58:00-07:00",
                "employer_known_at": "2026-07-15T00:05:00-07:00",
                "claimed_cause": "unknown",
            },
        ),
        (
            "CLM-771",
            "HOSP-A",
            {
                "case_id": "CASE-771",
                "scope": "medical_outcome",
                "medical_category": "inpatient_admission",
                "outcome_at": "2026-07-15T00:10:00-07:00",
                "employer_known_at": "2026-07-15T00:20:00-07:00",
                "claimed_cause": "unknown",
            },
        ),
        (
            "CLM-772",
            "CLINIC-B",
            {
                "case_id": "CASE-772",
                "scope": "medical_outcome",
                "medical_category": "medical_treatment_beyond_first_aid",
                "outcome_at": "2026-07-15T15:00:00-07:00",
                "employer_known_at": "2026-07-15T16:00:00-07:00",
                "claimed_cause": "employee_alleged_conveyor_contact",
            },
        ),
        (
            "CLM-773",
            "TEMP-X",
            {
                "case_id": "CASE-773",
                "scope": "medical_outcome",
                "medical_category": "inpatient_admission",
                "outcome_at": "2026-07-16T00:05:00-07:00",
                "employer_known_at": "2026-07-16T00:12:00-07:00",
                "claimed_cause": "unguarded_press",
            },
        ),
        (
            "CLM-774",
            "CORONER-C",
            {
                "case_id": "CASE-774",
                "scope": "fatality_outcome",
                "medical_category": "fatality",
                "outcome_at": "2026-06-05T08:00:00-07:00",
                "employer_known_at": "2026-06-05T08:20:00-07:00",
                "claimed_cause": "unknown",
            },
        ),
        (
            "CLM-775",
            "HOSP-A",
            {
                "case_id": "CASE-775",
                "scope": "medical_outcome",
                "medical_category": "inpatient_admission",
                "outcome_at": "2026-07-14T12:30:00-07:00",
                "employer_known_at": "2026-07-14T12:45:00-07:00",
                "claimed_cause": "unknown",
            },
        ),
        (
            "CLM-776-OLD",
            "HOSP-A",
            {
                "case_id": "CASE-776",
                "scope": "medical_outcome",
                "medical_category": "emergency_room_only",
                "outcome_at": "2026-07-16T00:00:00-07:00",
                "employer_known_at": "2026-07-16T00:05:00-07:00",
                "claimed_cause": "unknown",
            },
        ),
        (
            "CLM-776",
            "HOSP-A",
            {
                "case_id": "CASE-776",
                "scope": "medical_outcome",
                "medical_category": "inpatient_admission",
                "outcome_at": "2026-07-16T00:15:00-07:00",
                "employer_known_at": "2026-07-16T00:25:00-07:00",
                "claimed_cause": "unknown",
            },
        ),
    ]
    claims = [
        signed_claim(claim_id, issuer, payload, str(keys[issuer]))
        for claim_id, issuer, payload in claim_specs
    ]
    (WORKSPACE / "evidence/signed_outcomes.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in claims),
        encoding="utf-8",
    )

    events = [
        {
            "delivery_index": 1,
            "delivery_id": "DEL-001",
            "event_id": "EV-771-I",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-771",
            "stream": "incident",
            "sequence": 1,
            "claim_id": None,
        },
        {
            "delivery_index": 2,
            "delivery_id": "DEL-002",
            "event_id": "EV-771-O2",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-771",
            "stream": "medical_outcome",
            "sequence": 2,
            "claim_id": "CLM-771",
        },
        {
            "delivery_index": 3,
            "delivery_id": "DEL-003",
            "event_id": "EV-771-O2",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-771",
            "stream": "medical_outcome",
            "sequence": 2,
            "claim_id": "CLM-771",
        },
        {
            "delivery_index": 4,
            "delivery_id": "DEL-004",
            "event_id": "EV-771-O1",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-771",
            "stream": "medical_outcome",
            "sequence": 1,
            "claim_id": "CLM-771-OLD",
        },
        {
            "delivery_index": 5,
            "delivery_id": "DEL-005",
            "event_id": "EV-772-I",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-772",
            "stream": "incident",
            "sequence": 1,
            "claim_id": None,
        },
        {
            "delivery_index": 6,
            "delivery_id": "DEL-006",
            "event_id": "EV-772-O",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-772",
            "stream": "medical_outcome",
            "sequence": 1,
            "claim_id": "CLM-772",
        },
        {
            "delivery_index": 7,
            "delivery_id": "DEL-007",
            "event_id": "EV-773-O",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-773",
            "stream": "medical_outcome",
            "sequence": 1,
            "claim_id": "CLM-773",
        },
        {
            "delivery_index": 8,
            "delivery_id": "DEL-008",
            "event_id": "EV-773-I",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-773",
            "stream": "incident",
            "sequence": 1,
            "claim_id": None,
        },
        {
            "delivery_index": 9,
            "delivery_id": "DEL-009",
            "event_id": "EV-774-O",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-774",
            "stream": "medical_outcome",
            "sequence": 1,
            "claim_id": "CLM-774",
        },
        {
            "delivery_index": 10,
            "delivery_id": "DEL-010",
            "event_id": "EV-774-I",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-774",
            "stream": "incident",
            "sequence": 1,
            "claim_id": None,
        },
        {
            "delivery_index": 11,
            "delivery_id": "DEL-011",
            "event_id": "EV-775-I",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-775",
            "stream": "incident",
            "sequence": 1,
            "claim_id": None,
        },
        {
            "delivery_index": 12,
            "delivery_id": "DEL-012",
            "event_id": "EV-775-O",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-775",
            "stream": "medical_outcome",
            "sequence": 1,
            "claim_id": "CLM-775",
        },
        {
            "delivery_index": 13,
            "delivery_id": "DEL-013",
            "event_id": "EV-776-O2",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-776",
            "stream": "medical_outcome",
            "sequence": 2,
            "claim_id": "CLM-776",
        },
        {
            "delivery_index": 14,
            "delivery_id": "DEL-014",
            "event_id": "EV-776-O1",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-776",
            "stream": "medical_outcome",
            "sequence": 1,
            "claim_id": "CLM-776-OLD",
        },
        {
            "delivery_index": 15,
            "delivery_id": "DEL-015",
            "event_id": "EV-776-O2",
            "employer_id": "EMP-NORTHSTAR-17",
            "case_id": "CASE-776",
            "stream": "medical_outcome",
            "sequence": 2,
            "claim_id": "CLM-776",
        },
        {
            "delivery_index": 16,
            "delivery_id": "DEL-016",
            "event_id": "EV-FOREIGN",
            "employer_id": "EMP-OTHER-9",
            "case_id": "CASE-776",
            "stream": "incident",
            "sequence": 9,
            "claim_id": None,
        },
    ]
    (WORKSPACE / "evidence/event_deliveries.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events),
        encoding="utf-8",
    )

    database = WORKSPACE / "state/reporting.db"
    database.unlink(missing_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE case_facts(case_id TEXT PRIMARY KEY, incident_at TEXT NOT NULL, work_relatedness TEXT NOT NULL, employee_token TEXT NOT NULL);
            CREATE TABLE case_state(case_id TEXT PRIMARY KEY, recordability TEXT NOT NULL, osha_reporting_path TEXT NOT NULL, deadline_utc TEXT, medical_category TEXT NOT NULL, cause_status TEXT NOT NULL, workers_comp_action TEXT NOT NULL, version INTEGER NOT NULL);
            CREATE TABLE external_submissions(submission_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, channel TEXT NOT NULL, submitted_at_utc TEXT NOT NULL, receipt_id TEXT NOT NULL, observed_external INTEGER NOT NULL);
            CREATE TABLE event_receipts(delivery_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, disposition TEXT NOT NULL, recovery_id TEXT NOT NULL);
            CREATE TABLE report_queue(case_id TEXT, channel TEXT, action TEXT, boundary TEXT, status TEXT, recovery_id TEXT, external_action INTEGER NOT NULL, PRIMARY KEY(case_id, channel));
            CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY, status TEXT NOT NULL, source_checkpoint TEXT NOT NULL, semantic_digest TEXT NOT NULL, external_actions INTEGER NOT NULL);
            CREATE TABLE before_image_journal(journal_id INTEGER PRIMARY KEY, recovery_id TEXT NOT NULL, table_name TEXT NOT NULL, key_value TEXT NOT NULL, before_json TEXT NOT NULL, applied INTEGER NOT NULL);
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        cases = [
            (
                "CASE-771",
                "2026-07-14T23:42:00-07:00",
                "verified_work_related",
                "EMPLOYEE-771",
            ),
            (
                "CASE-772",
                "2026-07-15T14:10:00-07:00",
                "verified_work_related",
                "EMPLOYEE-772",
            ),
            ("CASE-773", "2026-07-15T22:55:00-07:00", "pending", "EMPLOYEE-773"),
            (
                "CASE-774",
                "2026-05-01T09:00:00-07:00",
                "verified_work_related",
                "EMPLOYEE-774",
            ),
            (
                "CASE-775",
                "2026-07-13T10:00:00-07:00",
                "verified_work_related",
                "EMPLOYEE-775",
            ),
            (
                "CASE-776",
                "2026-07-15T23:50:00-07:00",
                "verified_work_related",
                "EMPLOYEE-776",
            ),
        ]
        connection.executemany("INSERT INTO case_facts VALUES(?,?,?,?)", cases)
        initial = [
            (
                case_id,
                "unresolved",
                "unresolved",
                None,
                "unknown",
                "unverified_not_propagated",
                "hold_pending_evidence",
                1,
            )
            for case_id, *_ in cases
        ]
        connection.executemany(
            "INSERT INTO case_state VALUES(?,?,?,?,?,?,?,?)", initial
        )
        connection.execute(
            "INSERT INTO external_submissions VALUES(?,?,?,?,?,1)",
            (
                "SUB-771",
                "CASE-771",
                "OSHA",
                "2026-07-15T07:55:00Z",
                "OSHA-RCP-771",
            ),
        )
        interrupted = str(policy["recovery_id"])
        connection.execute(
            "INSERT INTO recovery_runs VALUES(?,?,?,?,0)",
            (
                interrupted,
                "interrupted",
                "stale-crash-checkpoint",
                "partial",
            ),
        )
        for journal_id, case_id in ((1, "CASE-772"), (2, "CASE-773")):
            row = connection.execute(
                "SELECT * FROM case_state WHERE case_id=?", (case_id,)
            ).fetchone()
            columns = [
                item[0]
                for item in connection.execute(
                    "SELECT * FROM case_state LIMIT 0"
                ).description
            ]
            before = dict(zip(columns, row, strict=True))
            connection.execute(
                "INSERT INTO before_image_journal VALUES(?,?,?,?,?,1)",
                (
                    journal_id,
                    interrupted,
                    "case_state",
                    case_id,
                    json.dumps(before, sort_keys=True),
                ),
            )
        connection.execute(
            "UPDATE case_state SET recordability='not_recordable',medical_category='first_aid',version=2 WHERE case_id='CASE-772'"
        )
        connection.execute(
            "UPDATE case_state SET cause_status='cause_asserted_from_unverified_note',medical_category='inpatient_admission',version=2 WHERE case_id='CASE-773'"
        )
        connection.execute(
            "INSERT INTO report_queue VALUES(?,?,?,?,?,?,1)",
            (
                "CASE-773",
                "OSHA",
                "submit_now",
                "external",
                "partially_sent",
                interrupted,
            ),
        )
        connection.execute("INSERT INTO system_state VALUES('source_revision','17')")
        connection.commit()

    manifest_files = {}
    for relative in (
        "policy/reporting_policy.json",
        "evidence/signed_outcomes.jsonl",
        "evidence/event_deliveries.jsonl",
    ):
        manifest_files[relative] = digest((WORKSPACE / relative).read_bytes())
    write_json(
        WORKSPACE / "policy/source_manifest.json",
        {"schema_version": 1, "files": manifest_files},
    )

    plan = {
        "schema_version": 1,
        "employer_id": "EMP-NORTHSTAR-17",
        "recovery_id": "REC-OSHA-2026-0716-A",
        "source_checkpoint": "PLACEHOLDER",
        "event_receipts": [
            {
                "delivery_id": row[0],
                "event_id": row[1],
                "case_id": row[2],
                "stream": row[3],
                "sequence": row[4],
                "disposition": row[5],
            }
            for row in [
                ("DEL-001", "EV-771-I", "CASE-771", "incident", 1, "applied_current"),
                (
                    "DEL-002",
                    "EV-771-O2",
                    "CASE-771",
                    "medical_outcome",
                    2,
                    "applied_current",
                ),
                (
                    "DEL-003",
                    "EV-771-O2",
                    "CASE-771",
                    "medical_outcome",
                    2,
                    "duplicate_delivery_ignored",
                ),
                (
                    "DEL-004",
                    "EV-771-O1",
                    "CASE-771",
                    "medical_outcome",
                    1,
                    "superseded_by_newer_sequence",
                ),
                ("DEL-005", "EV-772-I", "CASE-772", "incident", 1, "applied_current"),
                (
                    "DEL-006",
                    "EV-772-O",
                    "CASE-772",
                    "medical_outcome",
                    1,
                    "applied_current",
                ),
                (
                    "DEL-007",
                    "EV-773-O",
                    "CASE-773",
                    "medical_outcome",
                    1,
                    "invalid_authority_quarantined",
                ),
                ("DEL-008", "EV-773-I", "CASE-773", "incident", 1, "applied_current"),
                (
                    "DEL-009",
                    "EV-774-O",
                    "CASE-774",
                    "medical_outcome",
                    1,
                    "applied_current",
                ),
                ("DEL-010", "EV-774-I", "CASE-774", "incident", 1, "applied_current"),
                ("DEL-011", "EV-775-I", "CASE-775", "incident", 1, "applied_current"),
                (
                    "DEL-012",
                    "EV-775-O",
                    "CASE-775",
                    "medical_outcome",
                    1,
                    "applied_current",
                ),
                (
                    "DEL-013",
                    "EV-776-O2",
                    "CASE-776",
                    "medical_outcome",
                    2,
                    "applied_current",
                ),
                (
                    "DEL-014",
                    "EV-776-O1",
                    "CASE-776",
                    "medical_outcome",
                    1,
                    "superseded_by_newer_sequence",
                ),
                (
                    "DEL-015",
                    "EV-776-O2",
                    "CASE-776",
                    "medical_outcome",
                    2,
                    "duplicate_delivery_ignored",
                ),
                (
                    "DEL-016",
                    "EV-FOREIGN",
                    "CASE-776",
                    "incident",
                    9,
                    "employer_mismatch_ignored",
                ),
            ]
        ],
        "case_outcomes": [
            {
                "case_id": "CASE-771",
                "recordability": "recordable",
                "osha_reporting_path": "preserve_observed_submission",
                "deadline_utc": "2026-07-16T07:20:00Z",
                "medical_category": "inpatient_admission",
                "cause_status": "unverified_not_propagated",
                "workers_comp_action": "stage_notice_offline",
            },
            {
                "case_id": "CASE-772",
                "recordability": "recordable",
                "osha_reporting_path": "not_osha_reportable",
                "deadline_utc": None,
                "medical_category": "medical_treatment_beyond_first_aid",
                "cause_status": "unverified_not_propagated",
                "workers_comp_action": "stage_notice_offline",
            },
            {
                "case_id": "CASE-773",
                "recordability": "pending_evidence",
                "osha_reporting_path": "hold_pending_verified_outcome",
                "deadline_utc": None,
                "medical_category": "unknown",
                "cause_status": "unverified_not_propagated",
                "workers_comp_action": "hold_pending_evidence",
            },
            {
                "case_id": "CASE-774",
                "recordability": "recordable",
                "osha_reporting_path": "not_osha_reportable",
                "deadline_utc": None,
                "medical_category": "fatality",
                "cause_status": "unverified_not_propagated",
                "workers_comp_action": "stage_notice_offline",
            },
            {
                "case_id": "CASE-775",
                "recordability": "recordable",
                "osha_reporting_path": "not_osha_reportable",
                "deadline_utc": None,
                "medical_category": "inpatient_admission",
                "cause_status": "unverified_not_propagated",
                "workers_comp_action": "stage_notice_offline",
            },
            {
                "case_id": "CASE-776",
                "recordability": "recordable",
                "osha_reporting_path": "stage_osha_24h_report",
                "deadline_utc": "2026-07-17T07:25:00Z",
                "medical_category": "inpatient_admission",
                "cause_status": "unverified_not_propagated",
                "workers_comp_action": "stage_notice_offline",
            },
        ],
        "report_actions": [
            {
                "case_id": "CASE-771",
                "channel": "OSHA",
                "action": "preserve_observed_submission",
                "boundary": "observed_external_complete",
            },
            {
                "case_id": "CASE-776",
                "channel": "OSHA",
                "action": "stage_report_offline",
                "boundary": "pending_authorized_external_submit",
            },
        ],
        "external_actions_executed": False,
    }
    subprocess.run(
        ["python3", "injuryctl.py", "inspect", "--json"],
        cwd=WORKSPACE,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    checkpoint = json.loads((WORKSPACE / ".injury_inspect.json").read_text())[
        "source_checkpoint"
    ]
    (WORKSPACE / ".injury_inspect.json").unlink()
    plan["source_checkpoint"] = checkpoint
    write_json(REFERENCE / "recovery_plan.json", plan)
    temporary = TASK / "tests/.fixture-workspace"
    shutil.rmtree(temporary, ignore_errors=True)
    shutil.copytree(WORKSPACE, temporary)
    shutil.copy2(REFERENCE / "recovery_plan.json", temporary / "recovery_plan.json")
    for command in ("preview", "apply", "stage", "verify", "replay"):
        subprocess.run(
            ["python3", "injuryctl.py", command, "recovery_plan.json"],
            cwd=temporary,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
    for relative in (
        ".injury_preview.json",
        "state/reporting.db",
        "state/recovery_receipt.json",
        "staging/report_bundle.json",
        "staging/bundle_manifest.json",
        "state/verification.json",
        "state/replay_report.json",
    ):
        destination = REFERENCE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temporary / relative, destination)
    shutil.rmtree(temporary)


if __name__ == "__main__":
    main()
