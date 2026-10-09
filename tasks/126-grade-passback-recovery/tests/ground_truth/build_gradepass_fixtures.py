#!/usr/bin/env python3
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
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, object]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def create_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE students(student_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE sections(section_id TEXT PRIMARY KEY, course_code TEXT NOT NULL, term TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE enrollments(student_id TEXT NOT NULL, section_id TEXT NOT NULL, status TEXT NOT NULL, source_version INTEGER NOT NULL, PRIMARY KEY(student_id, section_id));
            CREATE TABLE identity_aliases(alias_type TEXT NOT NULL, external_id TEXT NOT NULL, canonical_id TEXT NOT NULL, relationship TEXT NOT NULL, PRIMARY KEY(alias_type, external_id));
            CREATE TABLE assignments(assignment_id TEXT PRIMARY KEY, section_id TEXT NOT NULL, lms_line_item_id TEXT NOT NULL, version INTEGER NOT NULL, title TEXT NOT NULL, points_possible INTEGER NOT NULL, due_at TEXT NOT NULL, late_accept_until TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE lms_attempts(attempt_id TEXT PRIMARY KEY, lms_user_id TEXT NOT NULL, lms_section_id TEXT NOT NULL, lms_line_item_id TEXT NOT NULL, assignment_version INTEGER NOT NULL, score_given INTEGER NOT NULL, score_maximum INTEGER NOT NULL, submitted_at TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE gradebook_results(student_id TEXT NOT NULL, assignment_id TEXT NOT NULL, score_given INTEGER NOT NULL, score_maximum INTEGER NOT NULL, submitted_at TEXT NOT NULL, source_event_id TEXT NOT NULL, passback_id TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL, manual_override INTEGER NOT NULL, PRIMARY KEY(student_id, assignment_id));
            CREATE TABLE processed_events(event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, source_sequence INTEGER NOT NULL, disposition TEXT NOT NULL, payload_hash TEXT NOT NULL, passback_id TEXT NOT NULL);
            CREATE TABLE quarantined_events(event_id TEXT PRIMARY KEY, reason_code TEXT NOT NULL, payload_hash TEXT NOT NULL, passback_id TEXT NOT NULL);
            CREATE TABLE recovery_runs(passback_id TEXT PRIMARY KEY, status TEXT NOT NULL, plan_hash TEXT NOT NULL, source_bundle_hash TEXT NOT NULL, semantic_db_hash TEXT NOT NULL, revision INTEGER NOT NULL, external_actions_executed INTEGER NOT NULL);
            CREATE TABLE rollback_rows(passback_id TEXT NOT NULL, table_name TEXT NOT NULL, record_key TEXT NOT NULL, before_json TEXT NOT NULL, restored INTEGER NOT NULL, PRIMARY KEY(passback_id, table_name, record_key));
            CREATE TABLE system_state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO students VALUES (?, ?, ?)", [
            ("STU-1001", "Avery Chen", "active"),
            ("STU-1002", "Blake Ortiz", "active"),
            ("STU-1003", "Casey Morgan", "active"),
            ("STU-1004", "Devon Shah", "active"),
            ("STU-1005", "Emery Brooks", "active"),
        ])
        connection.executemany("INSERT INTO sections VALUES (?, ?, ?, ?)", [
            ("SEC-MATH-8A", "MATH-ALG1", "2026-FALL", "active"),
            ("SEC-ENG-8B", "ENG-08", "2026-FALL", "active"),
        ])
        connection.executemany("INSERT INTO enrollments VALUES (?, ?, ?, ?)", [
            ("STU-1001", "SEC-MATH-8A", "active", 17),
            ("STU-1002", "SEC-MATH-8A", "active", 17),
            ("STU-1003", "SEC-ENG-8B", "active", 12),
            ("STU-1004", "SEC-MATH-8A", "active", 17),
            ("STU-1005", "SEC-ENG-8B", "active", 12),
        ])
        connection.executemany("INSERT INTO identity_aliases VALUES (?, ?, ?, ?)", [
            ("section", "lms-math-legacy", "SEC-MATH-8A", "section_rekey"),
            ("section", "lms-eng-8b", "SEC-ENG-8B", "direct_binding"),
            ("student", "lms-alice-old", "STU-1001", "student_rekey"),
            ("student", "lms-bob", "STU-1002", "direct_binding"),
            ("student", "lms-carol-old", "STU-1003", "student_rekey"),
            ("student", "lms-temp-440", "STU-1004", "merged_identity"),
            ("student", "lms-dave", "STU-1005", "direct_binding"),
        ])
        connection.executemany("INSERT INTO assignments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ("ASG-ALG-Q1-V1", "SEC-MATH-8A", "li-alg-q1", 1, "Linear equations quiz (archived)", 10, "2026-08-12T17:00:00Z", "2026-08-14T17:00:00Z", "archived"),
            ("ASG-ALG-Q1", "SEC-MATH-8A", "li-alg-q1", 2, "Linear equations quiz", 20, "2026-08-12T17:00:00Z", "2026-08-14T17:00:00Z", "active"),
            ("ASG-ESSAY-2", "SEC-ENG-8B", "li-essay-2", 3, "Evidence-based essay", 50, "2026-08-10T17:00:00Z", "2026-08-13T17:00:00Z", "active"),
        ])
        attempts = [
            ("ATT-ALICE-V1", "lms-alice-old", "lms-math-legacy", "li-alg-q1", 1, 9, 10, "2026-08-11T15:20:00Z", "graded"),
            ("ATT-ALICE-V2", "lms-alice-old", "lms-math-legacy", "li-alg-q1", 2, 17, 20, "2026-08-12T15:30:00Z", "graded"),
            ("ATT-BOB-BADSCALE", "lms-bob", "lms-math-legacy", "li-alg-q1", 2, 85, 100, "2026-08-12T15:35:00Z", "graded"),
            ("ATT-BOB-CORRECTED", "lms-bob", "lms-math-legacy", "li-alg-q1", 2, 18, 20, "2026-08-12T15:40:00Z", "graded"),
            ("ATT-TEMP-MERGED", "lms-temp-440", "lms-math-legacy", "li-alg-q1", 2, 19, 20, "2026-08-12T16:00:00Z", "graded"),
            ("ATT-CAROL-LATE", "lms-carol-old", "lms-eng-8b", "li-essay-2", 3, 44, 50, "2026-08-11T14:00:00Z", "graded"),
            ("ATT-DAVE-EXPIRED", "lms-dave", "lms-eng-8b", "li-essay-2", 3, 48, 50, "2026-08-14T09:00:00Z", "graded"),
            ("ATT-UNKNOWN", "lms-ghost", "lms-section-retired", "li-alg-q1", 2, 16, 20, "2026-08-12T12:00:00Z", "graded"),
        ]
        connection.executemany("INSERT INTO lms_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", attempts)
        base_rows = [
            ("STU-1001", "ASG-ALG-Q1", 12, 20, "2026-08-10T10:00:00Z", "evt-prior-a", "GP-PRIOR", "posted_local", 2, 0),
            ("STU-1002", "ASG-ALG-Q1", 15, 20, "2026-08-10T11:00:00Z", "evt-prior-b", "GP-PRIOR", "posted_local", 1, 0),
            ("STU-1003", "ASG-ESSAY-2", 40, 50, "2026-08-09T13:00:00Z", "evt-prior-c", "GP-PRIOR", "posted_local", 3, 0),
            ("STU-1005", "ASG-ESSAY-2", 46, 50, "2026-08-10T12:00:00Z", "registrar-manual-17", "REGISTRAR", "manual_override", 8, 1),
        ]
        connection.executemany("INSERT INTO gradebook_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", base_rows)
        before = dict(zip(
            ("student_id", "assignment_id", "score_given", "score_maximum", "submitted_at", "source_event_id", "passback_id", "status", "version", "manual_override"),
            base_rows[0], strict=True,
        ))
        connection.execute(
            "UPDATE gradebook_results SET score_given = 19, source_event_id = 'evt-interrupted-wrong', passback_id = 'GP-INTERRUPTED-20260817', version = 3 WHERE student_id = 'STU-1001' AND assignment_id = 'ASG-ALG-Q1'"
        )
        connection.execute(
            "INSERT INTO recovery_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("GP-INTERRUPTED-20260817", "applying", "interrupted-plan", "interrupted-source", "", 41, 0),
        )
        connection.execute(
            "INSERT INTO rollback_rows VALUES (?, 'gradebook_results', ?, ?, 0)",
            ("GP-INTERRUPTED-20260817", "STU-1001|ASG-ALG-Q1", json.dumps(before, sort_keys=True, separators=(",", ":"))),
        )
        connection.executemany("INSERT INTO system_state VALUES (?, ?)", [
            ("projection_revision", "41"),
            ("stage_state", "interrupted_apply_detected"),
        ])
        connection.commit()


def write_sources() -> None:
    policy = {
        "schema_version": 1,
        "passback_id": "GP-20260818-DISTRICT-01",
        "interrupted_passback_id": "GP-INTERRUPTED-20260817",
        "target_revision": 42,
        "accepted_dispositions": ["accepted_on_time", "accepted_late"],
        "disposition_vocabulary": ["accept", "quarantine"],
        "reason_code_vocabulary": [
            "accepted_on_time", "accepted_late", "unknown_identity",
            "inactive_enrollment", "unknown_assignment", "stale_assignment_version",
            "invalid_score_scale", "attempt_mismatch", "late_window_closed",
        ],
        "gradebook_action_vocabulary": ["upsert_local", "quarantine_local"],
        "external_action_vocabulary": ["none"],
        "external_publish_authorized": False,
        "notification_authorized": False,
    }
    identity = {
        "schema_version": 1,
        "section_rekeys": [
            {"external_id": "lms-math-legacy", "canonical_id": "SEC-MATH-8A", "relationship": "section_rekey"},
            {"external_id": "lms-eng-8b", "canonical_id": "SEC-ENG-8B", "relationship": "direct_binding"},
        ],
        "student_rekeys": [
            {"external_id": "lms-alice-old", "canonical_id": "STU-1001", "relationship": "student_rekey"},
            {"external_id": "lms-bob", "canonical_id": "STU-1002", "relationship": "direct_binding"},
            {"external_id": "lms-carol-old", "canonical_id": "STU-1003", "relationship": "student_rekey"},
            {"external_id": "lms-dave", "canonical_id": "STU-1005", "relationship": "direct_binding"},
        ],
        "student_merges": [
            {"external_id": "lms-temp-440", "canonical_id": "STU-1004", "relationship": "merged_identity"},
        ],
        "authority": "district_sis_identity_index_snapshot_17",
    }
    write_json(WORKSPACE / "policy/passback_policy.json", policy)
    write_json(WORKSPACE / "evidence/identity_rekeys.json", identity)
    events = [
        {"event_id": "evt-line-q-v1", "event_type": "line_item", "source_sequence": 1, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 1, "score_maximum": 10},
        {"event_id": "evt-line-q-v2", "event_type": "line_item", "source_sequence": 2, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 2, "score_maximum": 20},
        {"event_id": "evt-line-essay-v3", "event_type": "line_item", "source_sequence": 3, "lms_section_id": "lms-eng-8b", "lms_line_item_id": "li-essay-2", "assignment_version": 3, "score_maximum": 50},
        {"event_id": "evt-result-alice-v1", "event_type": "result", "source_sequence": 4, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 1, "score_maximum": 10, "attempt_id": "ATT-ALICE-V1", "lms_user_id": "lms-alice-old", "score_given": 9, "submitted_at": "2026-08-11T15:20:00Z"},
        {"event_id": "evt-result-alice-v2", "event_type": "result", "source_sequence": 5, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 2, "score_maximum": 20, "attempt_id": "ATT-ALICE-V2", "lms_user_id": "lms-alice-old", "score_given": 17, "submitted_at": "2026-08-12T15:30:00Z"},
        {"event_id": "evt-result-bob-badscale", "event_type": "result", "source_sequence": 6, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 2, "score_maximum": 100, "attempt_id": "ATT-BOB-BADSCALE", "lms_user_id": "lms-bob", "score_given": 85, "submitted_at": "2026-08-12T15:35:00Z"},
        {"event_id": "evt-result-bob-corrected", "event_type": "result", "source_sequence": 7, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 2, "score_maximum": 20, "attempt_id": "ATT-BOB-CORRECTED", "lms_user_id": "lms-bob", "score_given": 18, "submitted_at": "2026-08-12T15:40:00Z"},
        {"event_id": "evt-result-merged-student", "event_type": "result", "source_sequence": 8, "lms_section_id": "lms-math-legacy", "lms_line_item_id": "li-alg-q1", "assignment_version": 2, "score_maximum": 20, "attempt_id": "ATT-TEMP-MERGED", "lms_user_id": "lms-temp-440", "score_given": 19, "submitted_at": "2026-08-12T16:00:00Z"},
        {"event_id": "evt-result-carol-late", "event_type": "result", "source_sequence": 9, "lms_section_id": "lms-eng-8b", "lms_line_item_id": "li-essay-2", "assignment_version": 3, "score_maximum": 50, "attempt_id": "ATT-CAROL-LATE", "lms_user_id": "lms-carol-old", "score_given": 44, "submitted_at": "2026-08-11T14:00:00Z"},
        {"event_id": "evt-result-dave-expired", "event_type": "result", "source_sequence": 10, "lms_section_id": "lms-eng-8b", "lms_line_item_id": "li-essay-2", "assignment_version": 3, "score_maximum": 50, "attempt_id": "ATT-DAVE-EXPIRED", "lms_user_id": "lms-dave", "score_given": 48, "submitted_at": "2026-08-14T09:00:00Z"},
        {"event_id": "evt-result-unknown", "event_type": "result", "source_sequence": 11, "lms_section_id": "lms-section-retired", "lms_line_item_id": "li-alg-q1", "assignment_version": 2, "score_maximum": 20, "attempt_id": "ATT-UNKNOWN", "lms_user_id": "lms-ghost", "score_given": 16, "submitted_at": "2026-08-12T12:00:00Z"},
    ]
    delivery_order = [events[index] for index in (8, 1, 4, 10, 5, 0, 7, 3, 6, 2, 9, 4)]
    feed = "".join(json.dumps(row, sort_keys=True) + "\n" for row in delivery_order)
    (WORKSPACE / "evidence/grade_feed.jsonl").write_text(feed, encoding="utf-8")


def write_manifest() -> None:
    orders = {
        "students": "student_id", "sections": "section_id",
        "enrollments": "student_id, section_id", "identity_aliases": "alias_type, external_id",
        "assignments": "assignment_id", "lms_attempts": "attempt_id",
    }
    with sqlite3.connect(WORKSPACE / "state/gradepass.db") as connection:
        protected = {table: digest(canonical(rows(connection, table, order))) for table, order in orders.items()}
        cursor = connection.execute(
            "SELECT * FROM gradebook_results WHERE manual_override = 1 ORDER BY student_id, assignment_id"
        )
        columns = [item[0] for item in cursor.description]
        manual = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        protected["manual_overrides"] = digest(canonical(manual))
    files = {}
    for relative in (
        "gradepassctl.py", "policy/passback_policy.json",
        "evidence/identity_rekeys.json", "evidence/grade_feed.jsonl",
    ):
        files[relative] = digest((WORKSPACE / relative).read_bytes())
    write_json(WORKSPACE / "policy/source_manifest.json", {
        "schema_version": 1,
        "checkpoint_id": "GP-CHECKPOINT-20260818-012",
        "files": files,
        "protected_tables": protected,
    })


def generate_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hb126-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        spec = importlib.util.spec_from_file_location(
            "gradepass_outcome_reference", TASK / "tests/test_outcome.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load controller for reference generation")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plan = module._truth()["plan"]
        write_json(workspace / "recovery_plan.json", plan)
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", "gradepassctl.py", command, "recovery_plan.json"],
                cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        handoff = """# Registrar grade-passback recovery handoff

## Identity and assignment resolution

Checkpoint `GP-CHECKPOINT-20260818-012` was reconciled under stable recovery
identity `GP-20260818-DISTRICT-01`. The legacy section `lms-math-legacy` was
rekeyed to `SEC-MATH-8A`; the current English section remained `SEC-ENG-8B`.
Learners `lms-alice-old` and `lms-carol-old` used SIS rekeys, while temporary
identity `lms-temp-440` was merged into canonical learner `STU-1004`. Every
accepted learner has an active enrollment in the resolved section.

The current line-item bindings are `li-alg-q1` version 2 at 20 points and
`li-essay-2` version 3 at 50 points. Event `evt-result-alice-v1` was quarantined
because assignment version 1 is archived; it could not replace the current
grade. Exact repeated delivery `evt-result-alice-v2` was deduplicated and
journaled once. Unknown section/user event `evt-result-unknown` was quarantined
without inventing a roster identity.

## Score and time decisions

The attempt-backed current scores for Alice, Bob, and merged learner Devon were
accepted on time into the local projection. Bob's separate 85/100 event
`evt-result-bob-badscale` was quarantined as an invalid score scale before the
corrected 18/20 result was applied. Carol's 44/50 essay arrived after its due
time but within the published late-acceptance window, so it is recorded as
late. Emery's 48/50 result arrived after the late window and was quarantined;
the registrar's existing manual 46/50 override remains untouched.

## Recovery and control closure

The controller restored the partially changed Alice row from interrupted run
`GP-INTERRUPTED-20260817` before performing one atomic SQLite recovery. The
local gradebook, processed-event journal, quarantine journal, normalized plan
hash, source-bundle hash, and revision 42 all verified exactly. Staging produced
only a pending-registrar-review receipt. Replay of the semantically same plan
was a database-byte-stable and receipt-byte-stable no-op; the stable passback ID
also rejects a conflicting plan.

No LMS score POST, SIS API publish, parent-portal update, learner or instructor
message, registrar notification, email, or other external action was executed.
This handoff records an offline local projection and review boundary only.
"""
        (workspace / "registrar_handoff.md").write_text(handoff, encoding="utf-8")
        for relative in (
            "recovery_plan.json", ".gradepass_preview.json", "registrar_handoff.md",
            "state/gradepass.db", "state/verification.json", "state/stage_receipt.json",
            "state/replay_report.json",
        ):
            target = REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / relative, target)


def main() -> None:
    (WORKSPACE / "policy").mkdir(parents=True, exist_ok=True)
    (WORKSPACE / "evidence").mkdir(parents=True, exist_ok=True)
    (WORKSPACE / "state").mkdir(parents=True, exist_ok=True)
    for relative in (
        "recovery_plan.json",
        ".gradepass_preview.json",
        "registrar_handoff.md",
        "state/verification.json",
        "state/stage_receipt.json",
        "state/replay_report.json",
    ):
        path = WORKSPACE / relative
        if path.exists():
            path.unlink()
    write_sources()
    create_database(WORKSPACE / "state/gradepass.db")
    write_manifest()
    generate_reference()


if __name__ == "__main__":
    main()
