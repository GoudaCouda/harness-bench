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


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_workspace() -> None:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    for relative in ("policy", "evidence/store", "state", "staging"):
        (WORKSPACE / relative).mkdir(parents=True, exist_ok=True)

    policy = {
        "schema_version": 1,
        "incident_id": "INC-8842",
        "recovery_id": "IER-20260819-01",
        "source_revision": 19,
        "acquisition_phase_order": ["volatile", "identity", "dual_use_context", "disk"],
        "event_dispositions": [
            "applied_current",
            "superseded_by_newer_sequence",
            "duplicate_delivery_ignored",
            "identity_mismatch_ignored",
            "hash_mismatch_quarantined",
        ],
        "acquisition_actions": ["preserve_offline", "quarantine_hash_mismatch", "quarantine_chain_break"],
        "scope_actions": [
            "preserve_observed_isolation",
            "stage_session_disable",
            "preserve_account_scope",
            "analyst_review_no_containment",
            "observe_no_containment",
        ],
        "rules": {
            "deduplication": "first delivery of an event_id is authoritative; later deliveries are duplicates",
            "ordering": "after identity filtering and de-duplication, highest sequence per stream is current",
            "evidence": "verify blob sha256 and predecessor custody link before preservation",
            "dual_use": "signed dual-use tooling with a valid ticket but an operator mismatch remains ambiguous",
            "scope": "contain only the evidenced host or session; a session signal cannot disable its account",
            "recovery": "restore interrupted before-images before one atomic local projection",
            "external_boundary": "offline staging only; never isolate, disable, delete, contact, or clean an external system",
        },
    }
    write_json(WORKSPACE / "policy/incident_policy.json", policy)

    blobs = {
        "BLOB-MEM-17": b"synthetic volatile indicators: sha256:mal-77 process=invoice-viewer.exe\n",
        "BLOB-ID-7": b"synthetic token telemetry: session=sess-7x impossible_travel=true\n",
        "BLOB-DUAL-8": b"synthetic dual-use context: tool=remote-admin.exe ticket=CHG-208 operator_match=false\n",
        "BLOB-DISK-17": b"synthetic disk snapshot: host=ws-fin-17 cleanable_artifacts=2\n",
        "BLOB-BAD-9": b"tampered synthetic acquisition payload\n",
        "BLOB-CHAIN-8": b"synthetic follow-up capture with missing predecessor\n",
    }
    for blob_id, data in blobs.items():
        (WORKSPACE / f"evidence/store/{blob_id}.bin").write_bytes(data)

    events = [
        {"delivery_id": "DEL-001", "event_id": "EV-PROC-17-1", "stream": "host:ws-fin-17", "sequence": 1, "incident_id": "INC-8842", "target_type": "host", "target_id": "ws-fin-17", "signal": "suspicious_process", "blob_id": "BLOB-MEM-17"},
        {"delivery_id": "DEL-002", "event_id": "EV-DUAL-8-3", "stream": "host:ws-ops-08", "sequence": 3, "incident_id": "INC-8842", "target_type": "host", "target_id": "ws-ops-08", "signal": "dual_use_tool", "blob_id": "BLOB-DUAL-8"},
        {"delivery_id": "DEL-003", "event_id": "EV-PROC-17-2", "stream": "host:ws-fin-17", "sequence": 2, "incident_id": "INC-8842", "target_type": "host", "target_id": "ws-fin-17", "signal": "confirmed_malware_hash", "blob_id": "BLOB-MEM-17"},
        {"delivery_id": "DEL-004", "event_id": "EV-ID-7-4", "stream": "session:sess-7x", "sequence": 4, "incident_id": "INC-8842", "target_type": "session", "target_id": "sess-7x", "signal": "token_replay", "blob_id": "BLOB-ID-7"},
        {"delivery_id": "DEL-005", "event_id": "EV-PROC-17-2", "stream": "host:ws-fin-17", "sequence": 2, "incident_id": "INC-8842", "target_type": "host", "target_id": "ws-fin-17", "signal": "confirmed_malware_hash", "blob_id": "BLOB-MEM-17"},
        {"delivery_id": "DEL-006", "event_id": "EV-DUAL-8-2", "stream": "host:ws-ops-08", "sequence": 2, "incident_id": "INC-8842", "target_type": "host", "target_id": "ws-ops-08", "signal": "dual_use_tool", "blob_id": "BLOB-DUAL-8"},
        {"delivery_id": "DEL-007", "event_id": "EV-FOREIGN-99", "stream": "session:sess-7x", "sequence": 99, "incident_id": "INC-OTHER", "target_type": "session", "target_id": "sess-7x", "signal": "account_takeover", "blob_id": "BLOB-ID-7"},
        {"delivery_id": "DEL-008", "event_id": "EV-BAD-9", "stream": "host:ws-lab-09", "sequence": 1, "incident_id": "INC-8842", "target_type": "host", "target_id": "ws-lab-09", "signal": "unverified_payload", "blob_id": "BLOB-BAD-9"},
    ]
    (WORKSPACE / "evidence/events.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8"
    )
    write_json(
        WORKSPACE / "evidence/dual_use_context.json",
        {
            "ws-ops-08": {
                "binary_signed": True,
                "change_ticket": "CHG-208",
                "ticket_valid": True,
                "expected_operator": "svc-maint",
                "observed_operator": "user-7",
                "operator_match": False,
            }
        },
    )

    database = WORKSPACE / "state/incident.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE entities(entity_type TEXT, entity_id TEXT PRIMARY KEY, parent_account TEXT, observed_classification TEXT);
            CREATE TABLE evidence_catalog(blob_id TEXT PRIMARY KEY, relative_path TEXT, expected_sha256 TEXT, predecessor_blob_id TEXT, recorded_predecessor_sha256 TEXT, phase TEXT, target_type TEXT, target_id TEXT);
            CREATE TABLE acquisition_requests(request_id TEXT PRIMARY KEY, blob_id TEXT, phase TEXT, depends_on TEXT, target_type TEXT, target_id TEXT);
            CREATE TABLE acquisition_state(request_id TEXT PRIMARY KEY, status TEXT, preserved_sha256 TEXT, version INTEGER);
            CREATE TABLE containment_state(entity_type TEXT, entity_id TEXT PRIMARY KEY, status TEXT, observed_external INTEGER, version INTEGER);
            CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY, status TEXT, source_checkpoint TEXT, semantic_digest TEXT, external_actions INTEGER);
            CREATE TABLE before_image_journal(journal_id TEXT PRIMARY KEY, recovery_id TEXT, table_name TEXT, record_id TEXT, before_json TEXT, applied INTEGER);
            CREATE TABLE event_receipts(delivery_id TEXT PRIMARY KEY, event_id TEXT, disposition TEXT, recovery_id TEXT);
            CREATE TABLE scope_queue(entity_id TEXT PRIMARY KEY, entity_type TEXT, action TEXT, boundary TEXT, status TEXT, external_action INTEGER);
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT);
            """
        )
        connection.executemany(
            "INSERT INTO entities VALUES(?,?,?,?)",
            [
                ("host", "ws-fin-17", None, "confirmed"),
                ("host", "ws-ops-08", None, "ambiguous"),
                ("host", "ws-clean-03", None, "clean"),
                ("account", "user-7", None, "session_scoped_signal"),
                ("session", "sess-7x", "user-7", "compromised"),
                ("session", "sess-safe-2", "user-7", "clean"),
            ],
        )
        catalog = [
            ("BLOB-MEM-17", "evidence/store/BLOB-MEM-17.bin", sha(blobs["BLOB-MEM-17"]), None, None, "volatile", "host", "ws-fin-17"),
            ("BLOB-ID-7", "evidence/store/BLOB-ID-7.bin", sha(blobs["BLOB-ID-7"]), None, None, "identity", "session", "sess-7x"),
            ("BLOB-DUAL-8", "evidence/store/BLOB-DUAL-8.bin", sha(blobs["BLOB-DUAL-8"]), None, None, "dual_use_context", "host", "ws-ops-08"),
            ("BLOB-DISK-17", "evidence/store/BLOB-DISK-17.bin", sha(blobs["BLOB-DISK-17"]), "BLOB-MEM-17", sha(blobs["BLOB-MEM-17"]), "disk", "host", "ws-fin-17"),
            ("BLOB-BAD-9", "evidence/store/BLOB-BAD-9.bin", "0" * 64, None, None, "volatile", "host", "ws-lab-09"),
            ("BLOB-CHAIN-8", "evidence/store/BLOB-CHAIN-8.bin", sha(blobs["BLOB-CHAIN-8"]), "BLOB-MISSING", "f" * 64, "disk", "host", "ws-ops-08"),
        ]
        connection.executemany("INSERT INTO evidence_catalog VALUES(?,?,?,?,?,?,?,?)", catalog)
        connection.executemany(
            "INSERT INTO acquisition_requests VALUES(?,?,?,?,?,?)",
            [
                ("ACQ-MEM-17", "BLOB-MEM-17", "volatile", None, "host", "ws-fin-17"),
                ("ACQ-ID-7", "BLOB-ID-7", "identity", None, "session", "sess-7x"),
                ("ACQ-DUAL-8", "BLOB-DUAL-8", "dual_use_context", None, "host", "ws-ops-08"),
                ("ACQ-DISK-17", "BLOB-DISK-17", "disk", "ACQ-MEM-17", "host", "ws-fin-17"),
                ("ACQ-BAD-9", "BLOB-BAD-9", "volatile", None, "host", "ws-lab-09"),
                ("ACQ-CHAIN-8", "BLOB-CHAIN-8", "disk", "ACQ-DUAL-8", "host", "ws-ops-08"),
            ],
        )
        connection.executemany(
            "INSERT INTO acquisition_state VALUES(?,?,?,?)",
            [(request_id, "pending", None, 1) for request_id in ("ACQ-ID-7", "ACQ-DUAL-8", "ACQ-DISK-17", "ACQ-BAD-9", "ACQ-CHAIN-8")]
            + [("ACQ-MEM-17", "partial_copy", "unverified", 2)],
        )
        connection.executemany(
            "INSERT INTO containment_state VALUES(?,?,?,?,?)",
            [
                ("host", "ws-fin-17", "isolated_observed", 1, 5),
                ("host", "ws-ops-08", "active", 0, 2),
                ("host", "ws-clean-03", "active", 0, 1),
                ("account", "user-7", "active", 0, 3),
                ("session", "sess-7x", "disabled_local_partial", 0, 4),
                ("session", "sess-safe-2", "active", 0, 1),
            ],
        )
        before_acq = {"request_id": "ACQ-MEM-17", "status": "pending", "preserved_sha256": None, "version": 1}
        before_session = {"entity_type": "session", "entity_id": "sess-7x", "status": "active", "observed_external": 0, "version": 3}
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?)", ("IER-CRASH-00", "interrupted", None, None, 0))
        connection.executemany(
            "INSERT INTO before_image_journal VALUES(?,?,?,?,?,?)",
            [
                ("J-001", "IER-CRASH-00", "acquisition_state", "ACQ-MEM-17", canonical(before_acq).decode().strip(), 1),
                ("J-002", "IER-CRASH-00", "containment_state", "sess-7x", canonical(before_session).decode().strip(), 1),
            ],
        )
        connection.execute("INSERT INTO system_state VALUES('source_revision','19')")
        connection.commit()

    protected = [
        "policy/incident_policy.json",
        "evidence/events.jsonl",
        "evidence/dual_use_context.json",
        *[f"evidence/store/{name}.bin" for name in blobs],
    ]
    manifest = {name: sha((WORKSPACE / name).read_bytes()) for name in protected}
    write_json(WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": manifest})


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    shutil.copytree(WORKSPACE, REFERENCE)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(
        "incident_private_fixture_truth", TASK / "tests/test_outcome.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    truth = module.seed_truth()
    plan = {
        "schema_version": 1,
        "incident_id": truth["policy"]["incident_id"],
        "recovery_id": truth["policy"]["recovery_id"],
        "source_checkpoint": truth["checkpoint"],
        "event_dispositions": truth["events"],
        "acquisitions": [
            {
                key: value
                for key, value in row.items()
                if key not in {"relative_path", "actual_sha256"}
            }
            | {
                "evidence_refs": [
                    row["relative_path"], f"sha256:{row['actual_sha256']}"
                ]
            }
            for row in truth["acquisitions"]
        ],
        "scope_actions": truth["scope"],
        "external_actions_executed": False,
    }
    write_json(REFERENCE / "recovery_plan.json", plan)
    for command in ("preview", "apply", "stage", "verify", "replay"):
        subprocess.run(
            ["python3", "-B", "incidentctl.py", command, "recovery_plan.json"],
            cwd=REFERENCE,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
    (REFERENCE / "containment_handoff.md").write_text(
        """# Incident INC-8842 offline recovery handoff

The interrupted local run was restored from both before-images before a single
atomic projection. Deliveries were de-duplicated by event ID before sequence
authority was applied; the foreign incident and bad-hash payload were not used.

Volatile memory for `ws-fin-17` precedes its dependent disk snapshot. Each
preserved object is addressed by SHA-256, while the bad hash and broken
predecessor chain remain quarantined. `ws-ops-08` remains ambiguous: its signed
dual-use binary and valid ticket do not resolve the operator mismatch.

The source records show `ws-fin-17` was already isolated before this offline
task. The only pending identity containment is `sess-7x`; it is staged as a
session-level request and is not expanded to account `user-7` or its clean
session. No containment is staged for the ambiguous or clean hosts.

All controller changes are local evidence preservation and offline staging.
No host was isolated, no session or account was disabled, no evidence was
deleted, and no external containment, cleanup, contact, or notification
occurred in this task. Verification closes the bundle digest, database state,
source checkpoint, and semantic replay identity.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    controller_source = WORKSPACE / "incidentctl.py"
    saved = controller_source.read_bytes() if controller_source.exists() else None
    build_workspace()
    if saved is None:
        raise SystemExit("install incidentctl.py before building fixtures")
    controller_source.write_bytes(saved)
    build_reference()
