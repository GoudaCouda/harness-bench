#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
sys.dont_write_bytecode = True


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def signed(event_id: str, event_type: str, occurred_at: str, payload: dict[str, object], key_id: str, material: str) -> dict[str, object]:
    body: dict[str, object] = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "payload": payload,
    }
    return {**body, "key_id": key_id, "signature": digest(canonical(body) + material.encode())}


def build_sources() -> None:
    policy = {
        "schema_version": 1,
        "recovery_id": "LIMS-ACC-20260819-07",
        "evidence_batch_id": "COC-BATCH-20260819-AM",
        "as_of": "2026-08-19T14:00:00Z",
        "late_signature_grace_hours": 2,
        "accession_states": [
            "accepted_pending_analysis",
            "quarantine_temperature_excursion",
            "quarantine_custody_incomplete",
            "rejected_container_integrity",
            "rejected_preservation_failure",
            "rejected_holding_time",
        ],
        "decision_vocabulary": {
            "temperature_status": ["within_range", "excursion"],
            "preservation_status": ["compliant", "noncompliant"],
            "container_status": ["intact", "damaged"],
            "custody_status": ["complete", "late_signature_valid", "missing"],
            "holding_time_status": ["within_limit", "exceeded"],
            "next_local_action": [
                "stage_for_qa_accession_review",
                "retain_in_controlled_storage_for_qa",
                "isolate_for_qa_disposition",
            ],
            "external_action": ["none"],
            "local_mutations": sorted(
                {
                    "resolved_lab_label",
                    "alias_version",
                    "received_at",
                    "receipt_temperature_c",
                    "temperature_status",
                    "preservation_status",
                    "container_status",
                    "custody_status",
                    "holding_time_status",
                    "accession_state",
                    "source_event_digest",
                }
            ),
        },
        "evidence_locator_contract": {
            "event": "evidence/custody_events.jsonl#<event_id>",
            "suite_rule": "policy/accession_policy.json#suite_rules/<analysis_suite>",
            "required_categories": [
                "registration",
                "highest_authorized_alias",
                "custody_transfer",
                "receipt_observation",
                "suite_rule",
            ],
            "conditional_category": (
                "late_custody_signature when a pending custody transfer is "
                "completed by its checksum-bound signature"
            ),
        },
        "disposition_precedence": [
            {
                "when": "container_status == damaged",
                "accession_state": "rejected_container_integrity",
                "next_local_action": "isolate_for_qa_disposition",
            },
            {
                "when": "preservation_status == noncompliant",
                "accession_state": "rejected_preservation_failure",
                "next_local_action": "isolate_for_qa_disposition",
            },
            {
                "when": "holding_time_status == exceeded",
                "accession_state": "rejected_holding_time",
                "next_local_action": "isolate_for_qa_disposition",
            },
            {
                "when": "temperature_status == excursion",
                "accession_state": "quarantine_temperature_excursion",
                "next_local_action": "retain_in_controlled_storage_for_qa",
            },
            {
                "when": "custody_status == missing",
                "accession_state": "quarantine_custody_incomplete",
                "next_local_action": "retain_in_controlled_storage_for_qa",
            },
            {
                "when": "otherwise",
                "accession_state": "accepted_pending_analysis",
                "next_local_action": "stage_for_qa_accession_review",
            },
        ],
        "suite_rules": {
            "dissolved_metals": {
                "matrix": "surface_water",
                "temperature_c_range": [2, 6],
                "required_preservation": "nitric_acid",
                "required_container": "hdpe_bottle",
                "holding_time_hours": 4320,
            },
            "microbiology": {
                "matrix": "surface_water",
                "temperature_c_range": [2, 6],
                "required_preservation": "none",
                "required_container": "sterile_polypropylene",
                "holding_time_hours": 6,
            },
            "soil_voc": {
                "matrix": "soil",
                "temperature_c_range": [0, 6],
                "required_preservation": "methanol",
                "required_container": "glass_vial",
                "holding_time_hours": 48,
            },
            "nutrients": {
                "matrix": "surface_water",
                "temperature_c_range": [2, 6],
                "required_preservation": "sulfuric_acid",
                "required_container": "amber_glass",
                "holding_time_hours": 672,
            },
        },
        "external_action": "none",
        "stage_boundary": "local_only_pending_accession_qa_review",
    }
    write_json(WORKSPACE / "policy/accession_policy.json", policy)
    materials = {
        "field-coc-2026-q3": "synthetic-field-custody-material-v3",
        "receiving-2026-q3": "synthetic-receiving-material-v5",
        "qa-authorization-2026-q3": "synthetic-qa-authorization-material-v2",
    }
    trust = {
        "schema_version": 1,
        "verification_materials": materials,
        "offline_only": True,
        "synthetic_fixture": True,
    }
    write_json(WORKSPACE / "evidence/event_trust.json", trust)
    field_key = "field-coc-2026-q3"
    receipt_key = "receiving-2026-q3"
    qa_key = "qa-authorization-2026-q3"
    events: list[dict[str, object]] = []
    registrations = [
        ("041", "SMP-26-041", "RIV-A-0819", "PRJ-RIVER-17", "MUNI-NORTH", "surface_water", "dissolved_metals", "2026-08-19T07:10:00Z"),
        ("042", "SMP-26-042", "RIV-B-0819", "PRJ-RIVER-17", "MUNI-NORTH", "surface_water", "microbiology", "2026-08-19T08:30:00Z"),
        ("043", "SMP-26-043", "SOIL-C-0819", "PRJ-BROWNFIELD-08", "MUNI-WEST", "soil", "soil_voc", "2026-08-19T09:00:00Z"),
        ("044", "SMP-26-044", "RIV-D-0819", "PRJ-RIVER-17", "MUNI-NORTH", "surface_water", "nutrients", "2026-08-19T06:00:00Z"),
    ]
    for short, sample_id, label, project, client, matrix, suite, collected in registrations:
        events.append(
            signed(
                f"EVT-REG-{short}",
                "sample_registered",
                collected,
                {
                    "sample_id": sample_id,
                    "field_label": label,
                    "project_id": project,
                    "client_code": client,
                    "matrix": matrix,
                    "analysis_suite": suite,
                    "collected_at": collected,
                },
                field_key,
                materials[field_key],
            )
        )
    aliases = [
        ("041", "SMP-26-041", "RIV-A-0819", "LIMS-W-20260819-041", 1, "2026-08-19T10:35:00Z"),
        ("042", "SMP-26-042", "RIV-B-0819", "LIMS-M-20260819-042", 1, "2026-08-19T11:55:00Z"),
        ("043-A", "SMP-26-043", "SOIL-C-0819", "LIMS-S-20260819-034", 1, "2026-08-19T11:40:00Z"),
        ("043-B", "SMP-26-043", "SOIL-C-0819", "LIMS-S-20260819-043", 2, "2026-08-19T11:48:00Z"),
        ("044", "SMP-26-044", "RIV-D-0819", "LIMS-N-20260819-044", 1, "2026-08-19T06:55:00Z"),
    ]
    for short, sample_id, field_label, lab_label, version, at in aliases:
        events.append(
            signed(
                f"EVT-ALIAS-{short}",
                "label_alias",
                at,
                {
                    "sample_id": sample_id,
                    "field_label": field_label,
                    "lab_label": lab_label,
                    "alias_version": version,
                    "authorized_scope": "accession_label_only",
                },
                receipt_key,
                materials[receipt_key],
            )
        )
    custody_specs = [
        ("041", "SMP-26-041", "signed", "2026-08-19T10:32:00Z"),
        ("042", "SMP-26-042", "signed", "2026-08-19T11:50:00Z"),
        ("043", "SMP-26-043", "pending", "2026-08-19T11:50:00Z"),
        ("044", "SMP-26-044", "signed", "2026-08-19T06:50:00Z"),
    ]
    custody_043: dict[str, object] | None = None
    for short, sample_id, status, at in custody_specs:
        event = signed(
            f"EVT-COC-{short}",
            "custody_transfer",
            at,
            {
                "sample_id": sample_id,
                "from_role": "field_sampler",
                "to_role": "accession_receiver",
                "signature_status": status,
            },
            field_key,
            materials[field_key],
        )
        events.append(event)
        if short == "043":
            custody_043 = event
    assert custody_043 is not None
    custody_body = {key: value for key, value in custody_043.items() if key not in {"key_id", "signature"}}
    events.append(
        signed(
            "EVT-LATE-SIG-043",
            "late_custody_signature",
            "2026-08-19T13:05:00Z",
            {
                "sample_id": "SMP-26-043",
                "target_event_id": "EVT-COC-043",
                "target_checksum": digest(canonical(custody_body)),
                "signed_by_role": "field_sampler",
                "authorization": "complete_pending_custody_signature",
            },
            qa_key,
            materials[qa_key],
        )
    )
    receipts = [
        ("041", "SMP-26-041", "LIMS-W-20260819-041", "2026-08-19T10:40:00Z", 4.4, "nitric_acid", "hdpe_bottle", "intact"),
        ("042", "SMP-26-042", "LIMS-M-20260819-042", "2026-08-19T12:00:00Z", 8.1, "none", "sterile_polypropylene", "intact"),
        ("043", "SMP-26-043", "LIMS-S-20260819-043", "2026-08-19T12:00:00Z", 5.1, "methanol", "glass_vial", "intact"),
        ("044", "SMP-26-044", "LIMS-N-20260819-044", "2026-08-19T07:00:00Z", 4.8, "sulfuric_acid", "amber_glass", "cracked"),
    ]
    receipt_042: dict[str, object] | None = None
    for short, sample_id, label, at, temperature, preservation, container, state in receipts:
        event = signed(
            f"EVT-RECV-{short}",
            "receipt_observation",
            at,
            {
                "sample_id": sample_id,
                "label": label,
                "received_at": at,
                "temperature_c": temperature,
                "preservation": preservation,
                "container_type": container,
                "container_state": state,
            },
            receipt_key,
            materials[receipt_key],
        )
        events.append(event)
        if short == "042":
            receipt_042 = event
    assert receipt_042 is not None
    events.append(dict(receipt_042))
    by_id = {event["event_id"]: event for event in events if event is not receipt_042}
    ordered_ids = [
        "EVT-RECV-042",
        "EVT-REG-041",
        "EVT-ALIAS-043-A",
        "EVT-COC-044",
        "EVT-REG-044",
        "EVT-RECV-041",
        "EVT-COC-043",
        "EVT-ALIAS-041",
        "EVT-REG-043",
        "EVT-RECV-044",
        "EVT-COC-041",
        "EVT-ALIAS-044",
        "EVT-LATE-SIG-043",
        "EVT-REG-042",
        "EVT-ALIAS-043-B",
        "EVT-RECV-043",
        "EVT-COC-042",
        "EVT-ALIAS-042",
        "EVT-RECV-042",
    ]
    stream = [by_id[event_id] for event_id in ordered_ids]
    (WORKSPACE / "evidence/custody_events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in stream), encoding="utf-8"
    )
    protected = [
        "policy/accession_policy.json",
        "evidence/event_trust.json",
        "evidence/custody_events.jsonl",
    ]
    write_json(
        WORKSPACE / "policy/source_manifest.json",
        {
            "schema_version": 1,
            "files": {locator: digest((WORKSPACE / locator).read_bytes()) for locator in protected},
        },
    )


def build_database() -> None:
    path = WORKSPACE / "state/lims.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    initial = [
        ("SMP-26-041", "RIV-A-0819", "PRJ-RIVER-17", "MUNI-NORTH", "surface_water", "dissolved_metals", "", 0, "", None, "pending", "pending", "pending", "pending", "pending", "pending_evidence", "", 0, 0, "retained", "none", 5),
        ("SMP-26-042", "RIV-B-0819", "PRJ-RIVER-17", "MUNI-NORTH", "surface_water", "microbiology", "", 0, "", None, "pending", "pending", "pending", "pending", "pending", "pending_evidence", "", 0, 0, "retained", "none", 8),
        ("SMP-26-043", "SOIL-C-0819", "PRJ-BROWNFIELD-08", "MUNI-WEST", "soil", "soil_voc", "", 0, "", None, "pending", "pending", "pending", "pending", "pending", "pending_evidence", "", 0, 0, "retained", "none", 3),
        ("SMP-26-044", "RIV-D-0819", "PRJ-RIVER-17", "MUNI-NORTH", "surface_water", "nutrients", "", 0, "", None, "pending", "pending", "pending", "pending", "pending", "pending_evidence", "", 0, 0, "retained", "none", 6),
    ]
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE samples(
                sample_id TEXT PRIMARY KEY,
                field_label TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL,
                client_code TEXT NOT NULL,
                matrix TEXT NOT NULL,
                analysis_suite TEXT NOT NULL,
                resolved_lab_label TEXT NOT NULL,
                alias_version INTEGER NOT NULL,
                received_at TEXT NOT NULL,
                receipt_temperature_c REAL,
                temperature_status TEXT NOT NULL,
                preservation_status TEXT NOT NULL,
                container_status TEXT NOT NULL,
                custody_status TEXT NOT NULL,
                holding_time_status TEXT NOT NULL,
                accession_state TEXT NOT NULL,
                source_event_digest TEXT NOT NULL,
                analysis_started INTEGER NOT NULL CHECK(analysis_started=0),
                results_released INTEGER NOT NULL CHECK(results_released=0),
                disposal_state TEXT NOT NULL,
                notification_state TEXT NOT NULL,
                version INTEGER NOT NULL
            );
            CREATE TABLE accession_runs(
                recovery_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                source_checkpoint TEXT NOT NULL,
                semantic_plan_digest TEXT NOT NULL,
                semantic_db_digest TEXT NOT NULL,
                final_revision INTEGER NOT NULL,
                external_analysis_started INTEGER NOT NULL CHECK(external_analysis_started=0),
                notifications_sent INTEGER NOT NULL CHECK(notifications_sent=0),
                results_released INTEGER NOT NULL CHECK(results_released=0),
                disposal_executed INTEGER NOT NULL CHECK(disposal_executed=0)
            );
            CREATE TABLE accession_journal(
                journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recovery_id TEXT NOT NULL,
                sample_id TEXT NOT NULL,
                before_json TEXT NOT NULL,
                restored INTEGER NOT NULL CHECK(restored IN (0,1))
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", initial)
        cursor = connection.execute("SELECT * FROM samples WHERE sample_id='SMP-26-041'")
        columns = [item[0] for item in cursor.description]
        before = dict(zip(columns, cursor.fetchone(), strict=True))
        connection.execute(
            "INSERT INTO accession_runs VALUES ('LIMS-ACC-INTERRUPTED-20260818', 'interrupted', 'diagnostic-old-checkpoint', 'diagnostic-old-plan', '', 12, 0, 0, 0, 0)"
        )
        connection.execute(
            "INSERT INTO accession_journal(recovery_id, sample_id, before_json, restored) VALUES (?, ?, ?, 0)",
            ("LIMS-ACC-INTERRUPTED-20260818", "SMP-26-041", canonical(before).decode().strip()),
        )
        connection.execute(
            "UPDATE samples SET resolved_lab_label='PARTIAL-WRONG-041', alias_version=9, accession_state='accepted_pending_analysis', version=6 WHERE sample_id='SMP-26-041'"
        )
        connection.executemany(
            "INSERT INTO system_state VALUES (?, ?)",
            [("lims_revision", "12"), ("source_lims_revision", "12"), ("stage_state", "interrupted")],
        )
        connection.commit()


def load_controller():
    spec = importlib.util.spec_from_file_location("fixture_limsctl", WORKSPACE / "limsctl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load LIMS controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_reference() -> None:
    # The public controller intentionally exposes validation, not an answer
    # constructor. The checked-in hidden plan seeds this deterministic fixture
    # rebuild and is then exercised through every public workflow command.
    plan = json.loads(
        (REFERENCE / "accession_plan.json").read_text(encoding="utf-8")
    )
    controller = load_controller()
    plan["source_checkpoint"] = controller.inspection_contract()[
        "source_checkpoint"
    ]
    write_json(WORKSPACE / "accession_plan.json", plan)
    handoff = """# Environmental LIMS accession recovery handoff

## Evidence authority and identity

The protected COC-BATCH-20260819-AM stream was processed offline. Every unique event signature validated against the supplied trust material. File order was not treated as chronology, and the second byte-identical EVT-RECV-042 occurrence was collapsed without hiding a conflict. Field labels were joined to protected sample IDs, then the highest continuous authorized alias version controlled. In particular SMP-26-043 moved from the erroneous version-1 `LIMS-S-20260819-034` alias to version 2 `LIMS-S-20260819-043`.

EVT-COC-043 was recorded with a pending field signature. EVT-LATE-SIG-043 arrived 1 hour 15 minutes later, its target checksum binds the signed custody event, and it is inside the two-hour policy grace period. The resulting custody status is `late_signature_valid`, not an inferred or waived signature.

## Sample dispositions

- SMP-26-041 / RIV-A-0819 is `accepted_pending_analysis`: 4.4 C is within the 2–6 C range, nitric-acid preservation and the intact HDPE bottle comply, custody is complete, and the metals holding time is open.
- SMP-26-042 / RIV-B-0819 is `quarantine_temperature_excursion`: the sterile container, no-preservative rule, custody, and six-hour holding time comply, but 8.1 C exceeds the 2–6 C receipt range. It remains in controlled storage for QA review.
- SMP-26-043 / SOIL-C-0819 is `accepted_pending_analysis`: 5.1 C, methanol preservation, intact glass vial, 48-hour holding time, corrected alias, and the later checksum-bound custody signature comply.
- SMP-26-044 / RIV-D-0819 is `rejected_container_integrity`: temperature, sulfuric-acid preservation, custody, and holding time comply, but the amber-glass container was observed cracked. It is isolated only for QA disposition; it was not disposed.

## Recovery and closeout

The interrupted LIMS-ACC-INTERRUPTED-20260818 journal entry was restored before the four decisions were committed atomically under stable recovery ID LIMS-ACC-20260819-07 and its protected source checkpoint. Verification closed exact sample rows, protected project/client identity, journal restoration, a single current transaction, and local-only safety flags. The local receipt was staged pending accession QA review. Semantic replay with the same plan was database- and receipt-byte-stable.

No environmental analysis was started, no result was released, no sample was disposed, and no client notification or other external action occurred. `accepted_pending_analysis` is a local queue state only and does not authorize testing.
"""
    (WORKSPACE / "accession_handoff.md").write_text(handoff, encoding="utf-8")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        subprocess.run(["python3", "limsctl.py", command, "accession_plan.json"], cwd=WORKSPACE, check=True, stdout=subprocess.DEVNULL)
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    for locator in (
        "accession_plan.json",
        ".accession_preview.json",
        "accession_handoff.md",
        "state/lims.db",
        "state/verification.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
    ):
        destination = REFERENCE / locator
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORKSPACE / locator, destination)
    build_database()
    for locator in (
        "accession_plan.json",
        ".accession_preview.json",
        "accession_handoff.md",
        "state/verification.json",
        "state/recovery_receipt.json",
        "state/replay_report.json",
    ):
        (WORKSPACE / locator).unlink(missing_ok=True)


if __name__ == "__main__":
    build_sources()
    build_database()
    build_reference()
