from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
SEED = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def build_database() -> None:
    path = SEED / "state/credentials.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    accounts = [
        ("svc-api", "identity", "prod", 1, 8, "active", "M-API-8", "2026-08-19T02:14:10Z"),
        ("svc-billing", "payments", "prod", 1, 12, "active", None, "2026-08-18T19:21:00Z"),
        ("svc-catalog", "commerce", "prod", 0, 7, "active", None, "2026-08-10T11:00:00Z"),
        ("svc-metrics", "observability", "prod", 0, 2, "active", None, "2026-08-12T08:00:00Z"),
        ("svc-search", "discovery", "prod", 1, 12, "active", "M-SEARCH-12", "2026-08-19T02:16:44Z"),
        ("svc-vault", "platform", "staging", 1, 3, "active", None, "2026-08-18T17:30:00Z"),
        ("svc-worker", "fulfillment", "prod", 1, 5, "rotating", "partial-write", "2026-08-19T02:18:03Z"),
    ]
    markers = [
        (
            "M-API-8",
            "INC-CR-204",
            "svc-api",
            8,
            "2026-08-19T02:14:10Z",
            "sha256:marker-api-v8",
        ),
        (
            "M-SEARCH-12",
            "INC-CR-204",
            "svc-search",
            12,
            "2026-08-19T02:16:44Z",
            "sha256:marker-search-v12",
        ),
    ]
    worker_before = {
        "account_id": "svc-worker",
        "owner": "fulfillment",
        "environment": "prod",
        "compromised": 1,
        "durable_version": 4,
        "status": "active",
        "rotation_marker": None,
        "updated_at": "2026-08-18T22:45:00Z",
    }
    worker_after = {
        "account_id": "svc-worker",
        "owner": "fulfillment",
        "environment": "prod",
        "compromised": 1,
        "durable_version": 5,
        "status": "rotating",
        "rotation_marker": "partial-write",
        "updated_at": "2026-08-19T02:18:03Z",
    }
    queue_after = {
        "queue_id": "Q-PARTIAL-svc-worker",
        "account_id": "svc-worker",
        "target_version": 5,
        "status": "allocating",
        "requested_by_recovery": "REC-INC-CR-204-01",
        "executed": 0,
    }
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE accounts(
              account_id TEXT PRIMARY KEY, owner TEXT NOT NULL,
              environment TEXT NOT NULL, compromised INTEGER NOT NULL,
              durable_version INTEGER NOT NULL, status TEXT NOT NULL,
              rotation_marker TEXT, updated_at TEXT NOT NULL
            );
            CREATE TABLE durable_markers(
              marker_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL,
              account_id TEXT UNIQUE NOT NULL, target_version INTEGER NOT NULL,
              committed_at TEXT NOT NULL, proof_hash TEXT NOT NULL
            );
            CREATE TABLE rotation_queue(
              queue_id TEXT PRIMARY KEY, account_id TEXT UNIQUE NOT NULL,
              target_version INTEGER NOT NULL, status TEXT NOT NULL,
              requested_by_recovery TEXT NOT NULL, executed INTEGER NOT NULL
            );
            CREATE TABLE decision_receipts(
              recovery_id TEXT NOT NULL, account_id TEXT NOT NULL,
              classification TEXT NOT NULL, action TEXT NOT NULL,
              current_version INTEGER NOT NULL, target_version INTEGER NOT NULL,
              PRIMARY KEY(recovery_id,account_id)
            );
            CREATE TABLE recovery_runs(
              recovery_id TEXT PRIMARY KEY, source_checkpoint TEXT,
              semantic_plan_digest TEXT, semantic_state_digest TEXT,
              status TEXT NOT NULL
            );
            CREATE TABLE recovery_journal(
              journal_id TEXT PRIMARY KEY, recovery_id TEXT NOT NULL,
              table_name TEXT NOT NULL, record_id TEXT NOT NULL,
              before_json TEXT, after_json TEXT NOT NULL, restored INTEGER NOT NULL
            );
            CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """
        )
        connection.executemany(
            "INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?)", accounts
        )
        connection.executemany(
            "INSERT INTO durable_markers VALUES (?,?,?,?,?,?)", markers
        )
        connection.execute(
            "INSERT INTO rotation_queue VALUES (?,?,?,?,?,?)",
            tuple(
                queue_after[key]
                for key in (
                    "queue_id",
                    "account_id",
                    "target_version",
                    "status",
                    "requested_by_recovery",
                    "executed",
                )
            ),
        )
        connection.execute(
            "INSERT INTO recovery_runs VALUES (?,?,?,?,?)",
            ("REC-INC-CR-204-01", None, None, None, "interrupted"),
        )
        connection.executemany(
            "INSERT INTO recovery_journal VALUES (?,?,?,?,?,?,?)",
            [
                (
                    "J-401",
                    "REC-INC-CR-204-01",
                    "accounts",
                    "svc-worker",
                    canonical(worker_before).decode().strip(),
                    canonical(worker_after).decode().strip(),
                    0,
                ),
                (
                    "J-402",
                    "REC-INC-CR-204-01",
                    "rotation_queue",
                    "Q-PARTIAL-svc-worker",
                    None,
                    canonical(queue_after).decode().strip(),
                    0,
                ),
            ],
        )
        connection.executemany(
            "INSERT INTO system_state VALUES (?,?)",
            [
                ("source_revision", "41"),
                ("incident_status", "open"),
                ("last_checkpoint_revision", "17"),
            ],
        )


def build_manifest() -> None:
    files = [
        "policy/rotation_policy.json",
        "evidence/incident_scope.json",
        "evidence/validation.jsonl",
        "state/stale_checkpoint.json",
    ]
    manifest = {
        "schema_version": 1,
        "files": {
            name: hashlib.sha256((SEED / name).read_bytes()).hexdigest()
            for name in files
        },
    }
    (SEED / "policy/source_manifest.json").write_bytes(canonical(manifest))


def load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "task099_fixture_truth", TASK / "tests/test_outcome.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    with tempfile.TemporaryDirectory(prefix="hb099-build-") as temporary:
        root = Path(temporary) / "workspace"
        shutil.copytree(SEED, root)
        evaluator = load_evaluator()
        plan = evaluator.seed_truth()["plan"]
        (root / "recovery_plan.json").write_bytes(canonical(plan))
        for command in ("preview", "apply", "stage", "verify", "replay"):
            subprocess.run(
                ["python3", "credentialctl.py", command, "recovery_plan.json"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        handoff = """# Credential rotation incident recovery handoff

Incident INC-CR-204 was reconstructed offline under recovery
REC-INC-CR-204-02. Durable markers, not checkpoint claims or expected
validation targets, control completion. The checkpoint correctly records
svc-api but falsely marks svc-billing complete; it omits the durable completion
for svc-search. It also misclassifies clean svc-catalog, while svc-metrics is
correctly absent. The missing svc-vault entry remains pending.

svc-api version 8 and svc-search version 12 have incident-scoped durable
markers and observed validation, so both are preserve_committed and were not
replayed. svc-billing remains at version 12 for target 13, svc-vault remains at
version 3 for target 4, and svc-worker was restored from its recovery_journal
before-image to version 4 for target 5. These three accounts each have exactly
one local staged request. svc-catalog version 7 and svc-metrics version 2 are
clean preserve_unchanged accounts and were not queued.

Journal J-401 restored the svc-worker account before-image. Journal J-402
removed the partial queue insertion before the replacement queue was committed
atomically. The local rotation_queue bundle, queue_manifest, recovery_receipt,
and verification report close over the same semantic plan and state hashes.
The reordered-plan replay completed as an idempotent_noop with zero database
mutation.

No credential was rotated or revoked. No external service, account,
notification, production system, or incident state was changed, and the
incident remains open for an authorized future operator to execute, validate,
and monitor the three pending rotations.
"""
        (root / "credential_recovery_handoff.md").write_text(
            handoff, encoding="utf-8"
        )
        REFERENCE.mkdir(parents=True)
        for relative in (
            "recovery_plan.json",
            "credential_recovery_handoff.md",
            "state/credentials.db",
            "state/recovery_receipt.json",
            "state/verification.json",
            "state/replay_report.json",
            "staging/rotation_queue.json",
            "staging/queue_manifest.json",
        ):
            target = REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, target)


def main() -> None:
    build_database()
    build_manifest()
    build_reference()


if __name__ == "__main__":
    main()
