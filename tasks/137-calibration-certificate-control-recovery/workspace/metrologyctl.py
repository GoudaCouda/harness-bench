#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/calibration.db"
PLAN_FIELDS = {"schema_version", "recovery_id", "source_checkpoint", "decisions", "external_actions_executed"}
DECISION_FIELDS = {
    "job_id", "asset_id", "certificate_id", "authoritative_result_id",
    "reference_chain", "traceability_status", "error_abs",
    "expanded_uncertainty", "guard_band_margin", "measurement_decision",
    "certificate_action", "asset_action", "downstream_scope",
    "local_mutations", "evidence_refs",
}
SET_FIELDS = ("reference_chain", "downstream_scope", "local_mutations", "evidence_refs")
TABLE_ORDER = {
    "calibration_jobs": "job_id", "downstream_uses": "use_id",
    "control_assessments": "job_id", "recall_actions": "recovery_id,use_id",
    "recovery_runs": "recovery_id", "recovery_journal": "journal_id",
    "system_state": "key",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def protected_sources_ok() -> tuple[bool, dict[str, str]]:
    declared = load_json(ROOT / "policy/source_manifest.json").get("files", {})
    actual = {name: digest((ROOT / name).read_bytes()) for name in declared}
    return actual == declared, actual


def connect(readonly: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True) if readonly else sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if table not in TABLE_ORDER:
        raise ValueError(f"unsupported table: {table}")
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY {TABLE_ORDER[table]}")]


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def signed_events() -> tuple[list[dict[str, Any]], list[str], list[int]]:
    trust = load_json(ROOT / "evidence/event_trust.json")
    deliveries = [json.loads(line) for line in (ROOT / "evidence/metrology_events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    verified = []
    for row in deliveries:
        payload = {key: value for key, value in row.items() if key not in {"key_id", "signature"}}
        valid = (
            row.get("key_id") == trust.get("key_id")
            and row.get("signature") == digest(canonical(payload) + str(trust.get("verification_material", "")).encode())
        )
        if valid:
            verified.append(row)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in verified:
        grouped.setdefault(str(row.get("event_id")), []).append(row)
    unique, duplicates = [], []
    for event_id in sorted(grouped):
        group = grouped[event_id]
        forms = {canonical(row) for row in group}
        if len(forms) == 1:
            unique.append(group[0])
            if len(group) > 1:
                duplicates.append(event_id)
    by_sequence: dict[int, list[dict[str, Any]]] = {}
    for row in unique:
        by_sequence.setdefault(int(row["sequence"]), []).append(row)
    conflicts = [sequence for sequence, group in by_sequence.items() if len({canonical(row) for row in group}) > 1]
    usable = [row for row in unique if int(row["sequence"]) not in conflicts]
    return sorted(usable, key=lambda row: (int(row["sequence"]), str(row["event_id"]))), duplicates, sorted(conflicts)


def baseline(connection: sqlite3.Connection, table: str, key: str) -> list[dict[str, Any]]:
    current = {str(row[key]): row for row in rows(connection, table)}
    policy = load_json(ROOT / "policy/metrology_policy.json")
    runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs")}
    for journal in rows(connection, "recovery_journal"):
        run = runs.get(journal["recovery_id"])
        if journal["entity_type"] != table or not run:
            continue
        if (run["status"] == "interrupted" and not journal["restored"]) or journal["recovery_id"] == policy["recovery_id"]:
            before = json.loads(journal["before_json"])
            current[str(before[key])] = before
    return [current[item] for item in sorted(current)]


def source_checkpoint(connection: sqlite3.Connection) -> str:
    policy = load_json(ROOT / "policy/metrology_policy.json")
    existing = connection.execute("SELECT source_checkpoint FROM recovery_runs WHERE recovery_id=?", (policy["recovery_id"],)).fetchone()
    if existing:
        return str(existing[0])
    revision = int(connection.execute("SELECT value FROM system_state WHERE key='source_revision'").fetchone()[0])
    value = {
        "source_hashes": load_json(ROOT / "policy/source_manifest.json")["files"],
        "baseline_jobs": baseline(connection, "calibration_jobs", "job_id"),
        "baseline_uses": baseline(connection, "downstream_uses", "use_id"),
        "source_revision": revision,
    }
    return digest(canonical(value))


def attachment(event: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    relative = str(event.get("attachment", ""))
    path = ROOT / relative
    try:
        safe = path.resolve().is_relative_to(ROOT.resolve()) and path.is_file() and not path.is_symlink()
        if not safe or digest(path.read_bytes()) != event.get("attachment_sha256"):
            return None, False
        value = load_json(path)
        return value if isinstance(value, dict) else None, isinstance(value, dict)
    except (OSError, json.JSONDecodeError):
        return None, False


def decimal_number(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def validate_candidate(
    candidate: dict[str, Any],
    connection: sqlite3.Connection | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check a caller-authored plan and return runtime context only after success."""
    owned = connection is None
    connection = connection or connect(readonly=True)
    try:
        policy = load_json(ROOT / "policy/metrology_policy.json")
        events, duplicates, conflicts = signed_events()
        standards = {row["standard_id"]: row for row in load_json(ROOT / "evidence/reference_standards.json")["standards"]}
        recalls = {row["standard_id"]: row for row in events if row.get("kind") == "standard_recalled"}
        measurements: dict[str, list[dict[str, Any]]] = {}
        for row in events:
            if row.get("kind") in {"measurement_recorded", "measurement_corrected"}:
                measurements.setdefault(str(row["job_id"]), []).append(row)
        jobs = baseline(connection, "calibration_jobs", "job_id")
        uses = baseline(connection, "downstream_uses", "use_id")
        decisions, final_jobs = [], {}
        final_uses = {row["use_id"]: dict(row) for row in uses}
        for job in jobs:
            job_id, calibrated = job["job_id"], dt(job["calibrated_at_utc"])
            candidates = sorted(measurements.get(job_id, []), key=lambda row: int(row["sequence"]))
            event = candidates[-1] if candidates else None
            result, intact = attachment(event) if event else (None, False)
            chain = list(event.get("reference_chain", [])) if event else []
            chain_ok = bool(chain)
            for standard_id in chain:
                standard = standards.get(standard_id)
                recall = recalls.get(standard_id)
                usable = bool(
                    standard
                    and standard.get("recorded_status") == "valid"
                    and dt(standard["valid_from_utc"]) <= calibrated <= dt(standard["valid_to_utc"])
                    and not (recall and calibrated >= dt(recall["affected_from_utc"]))
                )
                if not usable:
                    chain_ok = False
                    break
            authoritative = event is not None and intact and result is not None and result.get("job_id") == job_id and int(event["sequence"]) not in conflicts
            if not authoritative:
                traceability, measurement_decision = "evidence_unavailable", "not_evaluable"
                error_abs = uncertainty = margin = None
                cert_action, asset_action = "hold_evidence_review", "hold_local_status"
            else:
                error = abs(Decimal(str(result["error"])))
                uncertainty_decimal = Decimal(str(result["expanded_uncertainty"]))
                tolerance = Decimal(str(job["tolerance"]))
                margin_decimal = tolerance - error - uncertainty_decimal
                error_abs, uncertainty, margin = map(decimal_number, (error, uncertainty_decimal, margin_decimal))
                measurement_decision = "accept" if margin_decimal >= 0 else "reject"
                traceability = "traceable" if chain_ok else "untraceable"
                if not chain_ok:
                    cert_action, asset_action = "revoke_reference_recall", "quarantine_local_status"
                elif measurement_decision == "reject":
                    cert_action, asset_action = "revoke_out_of_tolerance", "quarantine_local_status"
                else:
                    cert_action, asset_action = "affirm_valid", "release_local_status"
            downstream = []
            if cert_action.startswith("revoke_"):
                downstream = sorted(row["use_id"] for row in uses if row["job_id"] == job_id and dt(row["occurred_at_utc"]) >= calibrated)
                for use_id in downstream:
                    final_uses[use_id]["review_status"] = "recall_review_local"
            target_certificate = {
                "affirm_valid": "valid",
                "revoke_reference_recall": "revoked_reference_recall",
                "revoke_out_of_tolerance": "revoked_out_of_tolerance",
                "hold_evidence_review": "hold_evidence_review",
            }[cert_action]
            target_asset = {
                "release_local_status": "released",
                "quarantine_local_status": "quarantine_local",
                "hold_local_status": "hold_local",
            }[asset_action]
            mutations = ["control_assessment"]
            if job["certificate_status"] != target_certificate:
                mutations.append("certificate_status")
            if job["asset_status"] != target_asset:
                mutations.append("asset_status")
            if downstream:
                mutations.append("downstream_recall_review")
            refs = [f"state/calibration.db#calibration_jobs/{job_id}", "policy/metrology_policy.json#guard_band_rule"]
            if event:
                refs.extend([f"evidence/metrology_events.jsonl#{event['event_id']}", f"evidence/results/{event['result_id']}.json"])
            for standard_id in chain:
                refs.append(f"evidence/reference_standards.json#{standard_id}")
                if standard_id in recalls:
                    refs.append(f"evidence/metrology_events.jsonl#{recalls[standard_id]['event_id']}")
            decision = {
                "job_id": job_id, "asset_id": job["asset_id"], "certificate_id": job["certificate_id"],
                "authoritative_result_id": event["result_id"] if authoritative else None,
                "reference_chain": sorted(chain), "traceability_status": traceability,
                "error_abs": error_abs, "expanded_uncertainty": uncertainty,
                "guard_band_margin": margin, "measurement_decision": measurement_decision,
                "certificate_action": cert_action, "asset_action": asset_action,
                "downstream_scope": downstream, "local_mutations": sorted(mutations),
                "evidence_refs": sorted(set(refs)),
            }
            decisions.append(decision)
            final = dict(job)
            if final["certificate_status"] != target_certificate or final["asset_status"] != target_asset:
                final.update(certificate_status=target_certificate, asset_status=target_asset, version=int(final["version"]) + 1)
            final_jobs[job_id] = final
        plan = {
            "schema_version": 1, "recovery_id": policy["recovery_id"],
            "source_checkpoint": source_checkpoint(connection), "decisions": decisions,
            "external_actions_executed": False,
        }
        got = normalized_plan(candidate)
        target = normalized_plan(plan)
        problems: list[str] = []
        source_ok, _ = protected_sources_ok()
        if not source_ok:
            problems.append("plan/global field source_checkpoint differs [evidence: protected source manifest]")
        if set(candidate) != PLAN_FIELDS:
            problems.append("plan schema differs [evidence: output contract]")
        candidate_rows = candidate.get("decisions")
        if not isinstance(candidate_rows, list) or any(
            not isinstance(row, dict) or set(row) != DECISION_FIELDS
            for row in candidate_rows
        ):
            problems.append("decisions schema differs [evidence: output contract]")
        for field in ("schema_version", "recovery_id", "source_checkpoint", "external_actions_executed"):
            if got.get(field) != target.get(field):
                problems.append(f"plan/global field {field} differs [evidence: policy, signed events, SQLite baseline]")
        actual_rows = {
            str(row.get("job_id")): row
            for row in got.get("decisions", [])
            if isinstance(row, dict)
        }
        target_rows = {str(row["job_id"]): row for row in target["decisions"]}
        for job_id in sorted(set(actual_rows) | set(target_rows)):
            if job_id not in actual_rows or job_id not in target_rows:
                problems.append(f"decisions/{job_id} field presence differs [evidence: calibration register]")
                continue
            for field in sorted(DECISION_FIELDS):
                if actual_rows[job_id].get(field) != target_rows[job_id].get(field):
                    problems.append(f"decisions/{job_id} field {field} differs [evidence: signed event, result attachment, reference chain, and guard-band policy]")
        if problems:
            raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
        return got, {
            "policy": policy,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "baseline_jobs": jobs,
            "baseline_uses": uses,
            "source_revision": int(connection.execute("SELECT value FROM system_state WHERE key='source_revision'").fetchone()[0]),
        }
    finally:
        if owned:
            connection.close()


def normalized_plan(value: dict[str, Any]) -> dict[str, Any]:
    answer = dict(value)
    normalized = []
    for raw in value.get("decisions", []) if isinstance(value.get("decisions"), list) else []:
        row = dict(raw) if isinstance(raw, dict) else raw
        if isinstance(row, dict):
            for field in SET_FIELDS:
                if isinstance(row.get(field), list):
                    row[field] = sorted(row[field])
        normalized.append(row)
    answer["decisions"] = sorted(normalized, key=lambda row: str(row.get("job_id")) if isinstance(row, dict) else "")
    return answer


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = load_json(path)
    return validate_candidate(candidate)


def recover_interrupted(connection: sqlite3.Connection) -> list[str]:
    recovered = []
    for run in rows(connection, "recovery_runs"):
        if run["status"] != "interrupted":
            continue
        pending = connection.execute("SELECT journal_id,entity_type,entity_id,before_json FROM recovery_journal WHERE recovery_id=? AND restored=0 ORDER BY journal_id", (run["recovery_id"],)).fetchall()
        for journal_id, entity_type, entity_id, before_json in pending:
            if entity_type not in {"calibration_jobs", "downstream_uses"}:
                raise ValueError("interrupted journal contains unsupported entity")
            before = json.loads(before_json)
            columns = sorted(before)
            key = "job_id" if entity_type == "calibration_jobs" else "use_id"
            connection.execute(f"UPDATE {entity_type} SET {', '.join(f'{column}=?' for column in columns)} WHERE {key}=?", [before[column] for column in columns] + [entity_id])
            connection.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal_id,))
        connection.execute("UPDATE recovery_runs SET status='rolled_back_recovered' WHERE recovery_id=?", (run["recovery_id"],))
        recovered.append(run["recovery_id"])
    return recovered


def logical_digest(connection: sqlite3.Connection) -> str:
    value = {table: rows(connection, table) for table in ("calibration_jobs", "downstream_uses", "control_assessments", "recall_actions")}
    value["current_revision"] = connection.execute("SELECT value FROM system_state WHERE key='current_revision'").fetchone()[0]
    return digest(canonical(value))


def project_registers(
    plan: dict[str, Any], facts: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Apply an already validated candidate to recovered register rows."""
    jobs = {row["job_id"]: dict(row) for row in facts["baseline_jobs"]}
    uses = {row["use_id"]: dict(row) for row in facts["baseline_uses"]}
    certificate_status = {
        "affirm_valid": "valid",
        "revoke_reference_recall": "revoked_reference_recall",
        "revoke_out_of_tolerance": "revoked_out_of_tolerance",
        "hold_evidence_review": "hold_evidence_review",
    }
    asset_status = {
        "release_local_status": "released",
        "quarantine_local_status": "quarantine_local",
        "hold_local_status": "hold_local",
    }
    for decision in plan["decisions"]:
        job = jobs[decision["job_id"]]
        target_certificate = certificate_status[decision["certificate_action"]]
        target_asset = asset_status[decision["asset_action"]]
        if job["certificate_status"] != target_certificate or job["asset_status"] != target_asset:
            job.update(
                certificate_status=target_certificate,
                asset_status=target_asset,
                version=int(job["version"]) + 1,
            )
        for use_id in decision["downstream_scope"]:
            uses[use_id]["review_status"] = "recall_review_local"
    return jobs, uses


def preview(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    with connect(readonly=True) as connection:
        interrupted = [
            row["recovery_id"]
            for row in rows(connection, "recovery_runs")
            if row["status"] == "interrupted"
        ]
    value = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "valid",
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": digest(canonical(plan)),
        "duplicate_event_ids_ignored": facts["duplicates"], "conflicting_sequences": facts["conflicts"],
        "decision_count": len(plan["decisions"]),
        "interrupted_recoveries_pending": interrupted,
        "external_actions_executed": False,
    }
    write_json(ROOT / ".metrology_preview.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))


def apply(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    final_jobs, final_uses = project_registers(plan, facts)
    with connect() as connection:
        existing = connection.execute("SELECT status,source_checkpoint,semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if existing:
            if existing[1:] == (plan["source_checkpoint"], plan_hash) and existing[0] == "committed_local_control":
                print(json.dumps({"status": "idempotent", "recovery_id": plan["recovery_id"]}))
                return
            raise ValueError("semantic_plan_conflict: recovery identity already exists")
        connection.execute("BEGIN IMMEDIATE")
        recovered = recover_interrupted(connection)
        for decision in plan["decisions"]:
            job_id = decision["job_id"]
            current = dict(connection.execute("SELECT * FROM calibration_jobs WHERE job_id=?", (job_id,)).fetchone())
            connection.execute("INSERT INTO recovery_journal(recovery_id,entity_type,entity_id,before_json,restored) VALUES (?,?,?,?,0)", (plan["recovery_id"], "calibration_jobs", job_id, canonical(current).decode().strip()))
            final = final_jobs[job_id]
            columns = sorted(final)
            connection.execute(f"UPDATE calibration_jobs SET {', '.join(f'{column}=?' for column in columns)} WHERE job_id=?", [final[column] for column in columns] + [job_id])
        for use_id, final in final_uses.items():
            current_row = connection.execute("SELECT * FROM downstream_uses WHERE use_id=?", (use_id,)).fetchone()
            current = dict(current_row)
            if current != final:
                connection.execute("INSERT INTO recovery_journal(recovery_id,entity_type,entity_id,before_json,restored) VALUES (?,?,?,?,0)", (plan["recovery_id"], "downstream_uses", use_id, canonical(current).decode().strip()))
                connection.execute("UPDATE downstream_uses SET review_status=? WHERE use_id=?", (final["review_status"], use_id))
        connection.execute("DELETE FROM control_assessments")
        connection.execute("DELETE FROM recall_actions")
        for decision in plan["decisions"]:
            connection.execute("INSERT INTO control_assessments VALUES (?,?,?,?,?,?)", (decision["job_id"], decision["authoritative_result_id"], decision["traceability_status"], decision["measurement_decision"], None if decision["guard_band_margin"] is None else f"{decision['guard_band_margin']:.2f}", plan_hash))
            for use_id in decision["downstream_scope"]:
                connection.execute("INSERT INTO recall_actions VALUES (?,?,?)", (plan["recovery_id"], use_id, "recall_review_local"))
        final_revision = facts["source_revision"] + 1
        connection.execute("INSERT INTO recovery_runs VALUES (?,?,?,?,?,?,0)", (plan["recovery_id"], "committed_local_control", plan["source_checkpoint"], plan_hash, "", final_revision))
        connection.execute("UPDATE system_state SET value=? WHERE key='current_revision'", (str(final_revision),))
        connection.execute("UPDATE system_state SET value='committed_local_control' WHERE key='stage_state'")
        semantic_db = logical_digest(connection)
        connection.execute("UPDATE recovery_runs SET semantic_db_digest=? WHERE recovery_id=?", (semantic_db, plan["recovery_id"]))
        connection.commit()
    print(json.dumps({"status": "committed_local_control", "recovered_runs": recovered, "recovery_id": plan["recovery_id"]}, sort_keys=True))


def verification_payload(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with connect(readonly=True) as connection:
        semantic_db = logical_digest(connection)
    value = {
        "schema_version": 1, "recovery_id": plan["recovery_id"], "status": "pass",
        "checks": {
            "source_checkpoint_matches": True, "signed_events_verified": True,
            "duplicates_deduplicated": True, "reference_chains_evaluated": True,
            "attachment_integrity_checked": True, "decimal_guard_bands_exact": True,
            "interrupted_journal_recovered": True, "database_projection_exact": True,
            "single_committed_recovery": True, "local_only": True,
        },
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "semantic_db_digest": semantic_db, "final_revision": facts["source_revision"] + 1,
        "external_actions_executed": False,
    }
    return value, facts, plan_hash, semantic_db


def verify(plan_path: Path) -> None:
    value, facts, plan_hash, semantic_db = verification_payload(plan_path)
    plan, _ = validate_plan(plan_path)
    final_jobs, final_uses = project_registers(plan, facts)
    with connect(readonly=True) as connection:
        jobs = {row["job_id"]: row for row in rows(connection, "calibration_jobs")}
        uses = {row["use_id"]: row for row in rows(connection, "downstream_uses")}
        runs = {row["recovery_id"]: row for row in rows(connection, "recovery_runs")}
        journals = rows(connection, "recovery_journal")
        revision = connection.execute("SELECT value FROM system_state WHERE key='current_revision'").fetchone()[0]
    problems = []
    if jobs != final_jobs or uses != final_uses:
        problems.append("job or downstream-use projection differs")
    run = runs.get(facts["policy"]["recovery_id"], {})
    if run.get("status") != "committed_local_control" or run.get("semantic_plan_digest") != plan_hash or run.get("semantic_db_digest") != semantic_db:
        problems.append("committed recovery identity or digest differs")
    if any(row["status"] == "interrupted" for row in runs.values()) or any(not row["restored"] for row in journals if row["recovery_id"] != facts["policy"]["recovery_id"]):
        problems.append("interrupted recovery was not restored")
    if revision != str(facts["source_revision"] + 1):
        problems.append("revision differs")
    if problems:
        raise ValueError("verification failed:\n- " + "\n- ".join(problems))
    write_json(ROOT / "state/verification.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))


def stage(plan_path: Path) -> None:
    verification, facts, plan_hash, semantic_db = verification_payload(plan_path)
    plan, _ = validate_plan(plan_path)
    verification_path = ROOT / "state/verification.json"
    handoff_path = ROOT / "calibration_control_handoff.md"
    if load_json(verification_path) != verification:
        raise ValueError("run verify before stage; verification is missing or stale")
    if not handoff_path.is_file() or handoff_path.stat().st_size < 500:
        raise ValueError("write a substantive calibration_control_handoff.md before stage")
    core = {
        "schema_version": 1, "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": plan_hash,
        "semantic_db_digest": semantic_db, "verification_sha256": digest(verification_path.read_bytes()),
        "handoff_sha256": digest(handoff_path.read_bytes()), "stage_boundary": facts["policy"]["stage_boundary"],
        "external_actions_executed": False,
    }
    packet = {**core, "review_token": digest(canonical(core)), "status": "staged_offline_review"}
    write_json(ROOT / "state/review_packet.json", packet)
    print(json.dumps(packet, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    before_db = DB.read_bytes()
    packet_path = ROOT / "state/review_packet.json"
    before_packet = packet_path.read_bytes()
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    report = {
        "schema_version": 1, "recovery_id": load_json(plan_path)["recovery_id"], "status": "pass",
        "database_byte_stable": DB.read_bytes() == before_db,
        "review_packet_byte_stable": packet_path.read_bytes() == before_packet,
        "single_committed_recovery": True, "external_actions_executed": False,
    }
    if not report["database_byte_stable"] or not report["review_packet_byte_stable"]:
        raise ValueError("semantic replay changed committed artifacts")
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def inspect(as_json: bool) -> None:
    policy = load_json(ROOT / "policy/metrology_policy.json")
    events, duplicates, conflicts = signed_events()
    source_integrity, _ = protected_sources_ok()
    with connect(readonly=True) as connection:
        jobs = rows(connection, "calibration_jobs")
        runs = rows(connection, "recovery_runs")
        state = dict(connection.execute("SELECT key,value FROM system_state").fetchall())
        checkpoint = source_checkpoint(connection)
    value = {
        "recovery_id": policy["recovery_id"], "source_checkpoint": checkpoint,
        "protected_source_integrity": source_integrity,
        "verified_event_ids_in_sequence": [row["event_id"] for row in events],
        "duplicate_event_ids_ignored": duplicates, "conflicting_sequences": conflicts,
        "jobs": [{key: row[key] for key in ("job_id", "asset_id", "certificate_id", "calibrated_at_utc", "tolerance", "certificate_status", "asset_status", "version")} for row in jobs],
        "recovery_runs": [{"recovery_id": row["recovery_id"], "status": row["status"]} for row in runs],
        "system_state": state,
    }
    print(json.dumps(value, indent=2, sort_keys=True) if as_json else "\n".join(f"{key}: {item}" for key, item in value.items()))


def query(table: str) -> None:
    if table not in TABLE_ORDER:
        raise ValueError("query table must be one of: " + ", ".join(sorted(TABLE_ORDER)))
    with connect(readonly=True) as connection:
        print(json.dumps(rows(connection, table), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded offline calibration-certificate controller")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("table")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("plan")
    args = parser.parse_args()
    if args.command == "inspect":
        inspect(args.json)
    elif args.command == "query":
        query(args.table)
    else:
        globals()[args.command]((ROOT / args.plan).resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
