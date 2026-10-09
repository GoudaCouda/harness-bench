#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/reporting.db"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def table_rows(
    connection: sqlite3.Connection, table: str, order: str
) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def source_status(root: Path) -> tuple[bool, dict[str, str], dict[str, str]]:
    manifest = load_json(root / "policy/source_manifest.json")["files"]
    actual: dict[str, str] = {}
    valid = True
    for relative, expected in manifest.items():
        try:
            actual[relative] = sha((root / relative).read_bytes())
        except OSError:
            actual[relative] = "missing"
        valid &= actual[relative] == expected
    return valid, manifest, actual


def restored_case_state(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    state = {
        row["case_id"]: row for row in table_rows(connection, "case_state", "case_id")
    }
    interrupted = {
        row["recovery_id"]
        for row in table_rows(connection, "recovery_runs", "recovery_id")
        if row["status"] == "interrupted"
    }
    for journal in table_rows(connection, "before_image_journal", "journal_id"):
        if journal["recovery_id"] in interrupted and journal["applied"]:
            before = json.loads(journal["before_json"])
            state[before["case_id"]] = before
    return [state[key] for key in sorted(state)]


def authority_snapshot(root: Path) -> dict[str, Any]:
    policy = load_json(root / "policy/reporting_policy.json")
    valid_sources, _, source_hashes = source_status(root)
    events = read_jsonl(root / "evidence/event_deliveries.jsonl")
    claims = {
        row["claim_id"]: row
        for row in read_jsonl(root / "evidence/signed_outcomes.jsonl")
    }
    with sqlite3.connect(
        f"file:{root / 'state/reporting.db'}?mode=ro", uri=True
    ) as connection:
        connection.row_factory = sqlite3.Row
        facts = table_rows(connection, "case_facts", "case_id")
        submissions = table_rows(connection, "external_submissions", "submission_id")
        journals = table_rows(connection, "before_image_journal", "journal_id")
        revision = int(
            dict(connection.execute("SELECT key,value FROM system_state"))[
                "source_revision"
            ]
        )
        base_state = restored_case_state(connection)
    checkpoint_payload = {
        "source_hashes": source_hashes,
        "source_revision": revision,
        "case_facts": facts,
        "external_submissions": submissions,
        "before_image_journal": journals,
    }
    return {
        "valid_sources": valid_sources,
        "policy": policy,
        "events": events,
        "claims": claims,
        "facts": {row["case_id"]: row for row in facts},
        "submissions": submissions,
        "base_state": base_state,
        "source_checkpoint": sha(canonical(checkpoint_payload))
        if valid_sources
        else "invalid-source-bundle",
    }


def claim_is_authoritative(
    claim: dict[str, Any] | None, policy: dict[str, Any]
) -> bool:
    if not isinstance(claim, dict) or not isinstance(claim.get("payload"), dict):
        return False
    issuer = policy["authority_registry"].get(claim.get("issuer"), {})
    payload = claim["payload"]
    payload_digest = sha(canonical(payload))
    expected_signature = sha(
        f"{issuer.get('verification_secret', '')}:{payload_digest}".encode()
    )
    return bool(
        issuer.get("active")
        and payload.get("scope") in issuer.get("scopes", [])
        and claim.get("payload_sha256") == payload_digest
        and claim.get("signature") == expected_signature
    )


def event_disposition(snapshot: dict[str, Any], event: dict[str, Any]) -> str:
    events = snapshot["events"]
    first_index = min(
        row["delivery_index"] for row in events if row["event_id"] == event["event_id"]
    )
    if event["delivery_index"] != first_index:
        return "duplicate_delivery_ignored"
    if event["employer_id"] != snapshot["policy"]["employer_id"]:
        return "employer_mismatch_ignored"
    if event["stream"] == "medical_outcome" and not claim_is_authoritative(
        snapshot["claims"].get(event["claim_id"]), snapshot["policy"]
    ):
        return "invalid_authority_quarantined"
    eligible = []
    for candidate in events:
        if candidate["employer_id"] != snapshot["policy"]["employer_id"]:
            continue
        if (
            candidate["case_id"] != event["case_id"]
            or candidate["stream"] != event["stream"]
        ):
            continue
        if candidate["delivery_index"] != min(
            row["delivery_index"]
            for row in events
            if row["event_id"] == candidate["event_id"]
        ):
            continue
        if candidate["stream"] == "medical_outcome" and not claim_is_authoritative(
            snapshot["claims"].get(candidate["claim_id"]), snapshot["policy"]
        ):
            continue
        eligible.append(int(candidate["sequence"]))
    return (
        "applied_current"
        if int(event["sequence"]) == max(eligible)
        else "superseded_by_newer_sequence"
    )


def controlling_medical_payload(
    snapshot: dict[str, Any], case_id: str
) -> dict[str, Any] | None:
    selected: tuple[int, dict[str, Any]] | None = None
    seen: set[str] = set()
    for event in snapshot["events"]:
        if event["event_id"] in seen:
            continue
        seen.add(event["event_id"])
        if event["case_id"] != case_id or event["stream"] != "medical_outcome":
            continue
        if event["employer_id"] != snapshot["policy"]["employer_id"]:
            continue
        claim = snapshot["claims"].get(event["claim_id"])
        if not claim_is_authoritative(claim, snapshot["policy"]):
            continue
        pair = (int(event["sequence"]), claim["payload"])
        if selected is None or pair[0] > selected[0]:
            selected = pair
    return selected[1] if selected else None


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def case_value(snapshot: dict[str, Any], case_id: str, field: str) -> Any:
    fact = snapshot["facts"][case_id]
    payload = controlling_medical_payload(snapshot, case_id)
    category = payload.get("medical_category") if payload else "unknown"
    evidence_pending = (
        fact["work_relatedness"] != "verified_work_related" or payload is None
    )
    if field == "recordability":
        if evidence_pending:
            return "pending_evidence"
        return (
            "recordable"
            if category
            in snapshot["policy"]["recordability"]["recordable_medical_categories"]
            else "not_recordable"
        )
    if field == "medical_category":
        return category
    if field == "cause_status":
        return "unverified_not_propagated"
    if field == "workers_comp_action":
        return "hold_pending_evidence" if evidence_pending else "stage_notice_offline"
    observed = any(
        row["case_id"] == case_id
        and row["channel"] == "OSHA"
        and row["observed_external"]
        for row in snapshot["submissions"]
    )
    qualifies = False
    hours = 0
    if payload and category == "fatality":
        qualifies = utc(payload["outcome_at"]) - utc(fact["incident_at"]) <= timedelta(
            days=snapshot["policy"]["osha_reporting"][
                "fatality_must_occur_within_days_of_incident"
            ]
        )
        hours = snapshot["policy"]["osha_reporting"]["fatality_deadline_hours"]
    elif payload and category == "inpatient_admission":
        qualifies = utc(payload["outcome_at"]) - utc(fact["incident_at"]) <= timedelta(
            hours=snapshot["policy"]["osha_reporting"][
                "inpatient_must_occur_within_hours_of_incident"
            ]
        )
        hours = snapshot["policy"]["osha_reporting"]["inpatient_deadline_hours"]
    if field == "osha_reporting_path":
        if evidence_pending:
            return "hold_pending_verified_outcome"
        if observed and qualifies:
            return "preserve_observed_submission"
        if qualifies:
            return "stage_osha_24h_report"
        return "not_osha_reportable"
    if field == "deadline_utc":
        if not qualifies or payload is None:
            return None
        return (
            (utc(payload["employer_known_at"]) + timedelta(hours=hours))
            .isoformat()
            .replace("+00:00", "Z")
        )
    raise KeyError(field)


def semantic_plan(plan: dict[str, Any]) -> list[Any]:
    return [
        "injury-reporting-recovery-v1",
        plan.get("schema_version"),
        plan.get("employer_id"),
        plan.get("recovery_id"),
        plan.get("source_checkpoint"),
        sorted(
            plan.get("event_receipts", []), key=lambda row: str(row.get("delivery_id"))
        ),
        sorted(plan.get("case_outcomes", []), key=lambda row: str(row.get("case_id"))),
        sorted(
            plan.get("report_actions", []),
            key=lambda row: (str(row.get("case_id")), str(row.get("channel"))),
        ),
        plan.get("external_actions_executed"),
    ]


def validate_plan(root: Path, plan: Any) -> dict[str, Any]:
    snapshot = authority_snapshot(root)
    errors: dict[str, list[dict[str, str]]] = {
        name: []
        for name in ("plan", "event_receipts", "case_outcomes", "report_actions")
    }
    if not isinstance(plan, dict):
        errors["plan"].append(
            {"id": "*", "field": "$", "error": "plan must be a JSON object"}
        )
        return {"valid": False, "errors": errors, "semantic_digest": None}
    required = {
        "schema_version",
        "employer_id",
        "recovery_id",
        "source_checkpoint",
        "event_receipts",
        "case_outcomes",
        "report_actions",
        "external_actions_executed",
    }
    if set(plan) != required:
        errors["plan"].append(
            {
                "id": "*",
                "field": "$",
                "error": "top-level fields differ from the published schema",
            }
        )
    scalar_checks = {
        "schema_version": 1,
        "employer_id": snapshot["policy"]["employer_id"],
        "recovery_id": snapshot["policy"]["recovery_id"],
        "source_checkpoint": snapshot["source_checkpoint"],
        "external_actions_executed": False,
    }
    for field, expected in scalar_checks.items():
        if plan.get(field) != expected:
            errors["plan"].append(
                {
                    "id": "*",
                    "field": field,
                    "error": "value does not match current local authority",
                }
            )

    event_fields = {
        "delivery_id",
        "event_id",
        "case_id",
        "stream",
        "sequence",
        "disposition",
    }
    source_events = {row["delivery_id"]: row for row in snapshot["events"]}
    actual_events = plan.get("event_receipts")
    if not isinstance(actual_events, list):
        errors["event_receipts"].append(
            {"id": "*", "field": "$", "error": "must be an array"}
        )
        actual_events = []
    event_map = {
        str(row.get("delivery_id")): row
        for row in actual_events
        if isinstance(row, dict) and row.get("delivery_id")
    }
    if len(event_map) != len(actual_events):
        errors["event_receipts"].append(
            {
                "id": "*",
                "field": "delivery_id",
                "error": "duplicate or malformed object key",
            }
        )
    for identifier in sorted(set(event_map) | set(source_events)):
        if identifier not in source_events or identifier not in event_map:
            errors["event_receipts"].append(
                {
                    "id": identifier,
                    "field": "delivery_id",
                    "error": "unknown or missing object",
                }
            )
            continue
        actual = event_map[identifier]
        source = source_events[identifier]
        if set(actual) != event_fields:
            errors["event_receipts"].append(
                {"id": identifier, "field": "$", "error": "object fields differ"}
            )
        for field in ("delivery_id", "event_id", "case_id", "stream", "sequence"):
            if actual.get(field) != source[field]:
                errors["event_receipts"].append(
                    {
                        "id": identifier,
                        "field": field,
                        "error": "value conflicts with the source delivery",
                    }
                )
        if actual.get("disposition") != event_disposition(snapshot, source):
            errors["event_receipts"].append(
                {
                    "id": identifier,
                    "field": "disposition",
                    "error": "value violates event precedence",
                }
            )

    case_fields = {
        "case_id",
        "recordability",
        "osha_reporting_path",
        "deadline_utc",
        "medical_category",
        "cause_status",
        "workers_comp_action",
    }
    actual_cases = plan.get("case_outcomes")
    if not isinstance(actual_cases, list):
        errors["case_outcomes"].append(
            {"id": "*", "field": "$", "error": "must be an array"}
        )
        actual_cases = []
    case_map = {
        str(row.get("case_id")): row
        for row in actual_cases
        if isinstance(row, dict) and row.get("case_id")
    }
    if len(case_map) != len(actual_cases):
        errors["case_outcomes"].append(
            {
                "id": "*",
                "field": "case_id",
                "error": "duplicate or malformed object key",
            }
        )
    for case_id in sorted(set(case_map) | set(snapshot["facts"])):
        if case_id not in snapshot["facts"] or case_id not in case_map:
            errors["case_outcomes"].append(
                {
                    "id": case_id,
                    "field": "case_id",
                    "error": "unknown or missing object",
                }
            )
            continue
        actual = case_map[case_id]
        if set(actual) != case_fields:
            errors["case_outcomes"].append(
                {"id": case_id, "field": "$", "error": "object fields differ"}
            )
        for field in sorted(case_fields - {"case_id"}):
            if actual.get(field) != case_value(snapshot, case_id, field):
                errors["case_outcomes"].append(
                    {
                        "id": case_id,
                        "field": field,
                        "error": "value violates source-derived reporting rule",
                    }
                )

    action_fields = {"case_id", "channel", "action", "boundary"}
    actual_actions = plan.get("report_actions")
    if not isinstance(actual_actions, list):
        errors["report_actions"].append(
            {"id": "*", "field": "$", "error": "must be an array"}
        )
        actual_actions = []
    action_map = {
        str(row.get("case_id")): row
        for row in actual_actions
        if isinstance(row, dict) and row.get("case_id")
    }
    eligible_ids = {
        case_id
        for case_id in snapshot["facts"]
        if case_value(snapshot, case_id, "osha_reporting_path")
        in {"preserve_observed_submission", "stage_osha_24h_report"}
    }
    if len(action_map) != len(actual_actions):
        errors["report_actions"].append(
            {
                "id": "*",
                "field": "case_id",
                "error": "duplicate or malformed object key",
            }
        )
    for case_id in sorted(set(action_map) | eligible_ids):
        if case_id not in eligible_ids or case_id not in action_map:
            errors["report_actions"].append(
                {
                    "id": case_id,
                    "field": "case_id",
                    "error": "unknown or missing report action",
                }
            )
            continue
        actual = action_map[case_id]
        if set(actual) != action_fields:
            errors["report_actions"].append(
                {"id": case_id, "field": "$", "error": "object fields differ"}
            )
        path = case_value(snapshot, case_id, "osha_reporting_path")
        checks = {
            "channel": "OSHA",
            "action": "preserve_observed_submission"
            if path == "preserve_observed_submission"
            else "stage_report_offline",
            "boundary": "observed_external_complete"
            if path == "preserve_observed_submission"
            else "pending_authorized_external_submit",
        }
        for field, expected in checks.items():
            if actual.get(field) != expected:
                errors["report_actions"].append(
                    {
                        "id": case_id,
                        "field": field,
                        "error": "value violates submission boundary",
                    }
                )
    valid = snapshot["valid_sources"] and not any(errors.values())
    return {
        "valid": valid,
        "errors": errors,
        "semantic_digest": sha(canonical(semantic_plan(plan))) if valid else None,
    }


def read_plan(relative: str) -> Any:
    path = (ROOT / relative).resolve()
    if ROOT not in path.parents or path == ROOT:
        raise ValueError("plan path must stay inside the workspace")
    return load_json(path)


def preview(relative: str) -> None:
    try:
        result = validate_plan(ROOT, read_plan(relative))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "valid": False,
            "errors": {
                "plan": [{"id": "*", "field": "$", "error": f"cannot read plan: {exc}"}]
            },
            "semantic_digest": None,
        }
    write_json(ROOT / ".injury_preview.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(2)


def restore_interrupted(connection: sqlite3.Connection, recovery_id: str) -> None:
    row = connection.execute(
        "SELECT status FROM recovery_runs WHERE recovery_id=?", (recovery_id,)
    ).fetchone()
    if row != ("interrupted",):
        return
    for table_name, before_json, applied in connection.execute(
        "SELECT table_name,before_json,applied FROM before_image_journal WHERE recovery_id=? ORDER BY journal_id",
        (recovery_id,),
    ):
        if table_name != "case_state" or not applied:
            continue
        before = json.loads(before_json)
        connection.execute(
            "UPDATE case_state SET recordability=?,osha_reporting_path=?,deadline_utc=?,medical_category=?,cause_status=?,workers_comp_action=?,version=? WHERE case_id=?",
            (
                before["recordability"],
                before["osha_reporting_path"],
                before["deadline_utc"],
                before["medical_category"],
                before["cause_status"],
                before["workers_comp_action"],
                before["version"],
                before["case_id"],
            ),
        )
    connection.execute("DELETE FROM report_queue WHERE recovery_id=?", (recovery_id,))
    connection.execute("DELETE FROM recovery_runs WHERE recovery_id=?", (recovery_id,))


def apply_plan(relative: str, replay_only: bool = False) -> None:
    plan = read_plan(relative)
    result = validate_plan(ROOT, plan)
    if not result["valid"]:
        write_json(ROOT / ".injury_preview.json", result)
        raise SystemExit("plan invalid; inspect .injury_preview.json")
    identity = plan["recovery_id"]
    semantic_digest = result["semantic_digest"]
    with sqlite3.connect(DB) as connection:
        existing = connection.execute(
            "SELECT status,source_checkpoint,semantic_digest FROM recovery_runs WHERE recovery_id=?",
            (identity,),
        ).fetchone()
        if existing and existing[0] == "applied_local":
            if existing[1:] == (plan["source_checkpoint"], semantic_digest):
                if replay_only:
                    write_json(
                        ROOT / "state/replay_report.json",
                        {
                            "recovery_id": identity,
                            "status": "semantic_noop",
                            "semantic_digest": semantic_digest,
                        },
                    )
                    print("semantic replay: no database mutation")
                    return
                print("already applied: semantic no-op")
                return
            raise SystemExit("recovery identity conflict; database unchanged")
        if replay_only:
            raise SystemExit("no applied recovery exists; use apply first")
        connection.execute("BEGIN IMMEDIATE")
        restore_interrupted(connection, identity)
        for row in plan["case_outcomes"]:
            connection.execute(
                "UPDATE case_state SET recordability=?,osha_reporting_path=?,deadline_utc=?,medical_category=?,cause_status=?,workers_comp_action=?,version=version+1 WHERE case_id=?",
                (
                    row["recordability"],
                    row["osha_reporting_path"],
                    row["deadline_utc"],
                    row["medical_category"],
                    row["cause_status"],
                    row["workers_comp_action"],
                    row["case_id"],
                ),
            )
            if row["workers_comp_action"] == "stage_notice_offline":
                connection.execute(
                    "INSERT INTO report_queue VALUES(?,?,?,?,?,?,0)",
                    (
                        row["case_id"],
                        "WORKERS_COMP",
                        "stage_notice_offline",
                        "pending_authorized_external_submit",
                        "staged_local",
                        identity,
                    ),
                )
        for row in plan["event_receipts"]:
            connection.execute(
                "INSERT INTO event_receipts VALUES(?,?,?,?)",
                (row["delivery_id"], row["event_id"], row["disposition"], identity),
            )
        for row in plan["report_actions"]:
            connection.execute(
                "INSERT INTO report_queue VALUES(?,?,?,?,?,?,0)",
                (
                    row["case_id"],
                    row["channel"],
                    row["action"],
                    row["boundary"],
                    "observed_only"
                    if row["action"] == "preserve_observed_submission"
                    else "staged_local",
                    identity,
                ),
            )
        connection.execute(
            "INSERT INTO recovery_runs VALUES(?,?,?,?,0)",
            (identity, "applied_local", plan["source_checkpoint"], semantic_digest),
        )
        connection.commit()
    write_json(
        ROOT / "state/recovery_receipt.json",
        {
            "recovery_id": identity,
            "source_checkpoint": plan["source_checkpoint"],
            "semantic_digest": semantic_digest,
            "status": "applied_local",
            "external_actions_executed": False,
        },
    )
    print("local injury-reporting projection applied")


def stage(relative: str) -> None:
    plan = read_plan(relative)
    result = validate_plan(ROOT, plan)
    if not result["valid"]:
        raise SystemExit("plan invalid")
    with sqlite3.connect(DB) as connection:
        applied = connection.execute(
            "SELECT status,semantic_digest FROM recovery_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
    if applied != ("applied_local", result["semantic_digest"]):
        raise SystemExit("matching local apply required before stage")
    osha = [
        {
            "case_id": row["case_id"],
            "deadline_utc": case_value(
                authority_snapshot(ROOT), row["case_id"], "deadline_utc"
            ),
            "status": "staged_local",
        }
        for row in plan["report_actions"]
        if row["action"] == "stage_report_offline"
    ]
    workers_comp = [
        {"case_id": row["case_id"], "status": "staged_local"}
        for row in plan["case_outcomes"]
        if row["workers_comp_action"] == "stage_notice_offline"
    ]
    bundle = {
        "recovery_id": plan["recovery_id"],
        "osha_reports": sorted(osha, key=lambda row: row["case_id"]),
        "workers_comp_notices": sorted(workers_comp, key=lambda row: row["case_id"]),
        "contains_private_medical_detail": False,
        "external_delivery": False,
    }
    write_json(ROOT / "staging/report_bundle.json", bundle)
    write_json(
        ROOT / "staging/bundle_manifest.json",
        {
            "bundle_sha256": sha(canonical(bundle)),
            "semantic_digest": result["semantic_digest"],
            "external_delivery": False,
        },
    )
    print("minimal offline reports staged")


def verify(relative: str) -> None:
    plan = read_plan(relative)
    result = validate_plan(ROOT, plan)
    errors = []
    bundle = load_json(ROOT / "staging/report_bundle.json")
    manifest = load_json(ROOT / "staging/bundle_manifest.json")
    if manifest.get("bundle_sha256") != sha(canonical(bundle)):
        errors.append("bundle digest mismatch")
    with sqlite3.connect(DB) as connection:
        receipt_count = connection.execute(
            "SELECT COUNT(*) FROM event_receipts WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()[0]
        external_count = (
            connection.execute(
                "SELECT COUNT(*) FROM report_queue WHERE external_action != 0"
            ).fetchone()[0]
            + connection.execute(
                "SELECT COUNT(*) FROM recovery_runs WHERE external_actions != 0"
            ).fetchone()[0]
        )
        duplicate_osha = connection.execute(
            "SELECT COUNT(*) FROM report_queue WHERE case_id='CASE-771' AND channel='OSHA' AND action!='preserve_observed_submission'"
        ).fetchone()[0]
    if receipt_count != len(plan["event_receipts"]):
        errors.append("event receipt closure mismatch")
    if external_count:
        errors.append("external action boundary violated")
    if duplicate_osha:
        errors.append("observed OSHA submission was duplicated")
    verification = {
        "verified": result["valid"] and not errors,
        "errors": errors,
        "source_checkpoint": plan["source_checkpoint"],
        "semantic_digest": result["semantic_digest"],
        "bundle_sha256": manifest.get("bundle_sha256"),
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/verification.json", verification)
    print(json.dumps(verification, indent=2, sort_keys=True))
    if not verification["verified"]:
        raise SystemExit(2)


def inspect(write_artifact: bool) -> None:
    snapshot = authority_snapshot(ROOT)
    with sqlite3.connect(DB) as connection:
        summary = {
            "source_manifest_valid": snapshot["valid_sources"],
            "source_checkpoint": snapshot["source_checkpoint"],
            "tables": {
                name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in (
                    "case_facts",
                    "case_state",
                    "external_submissions",
                    "event_receipts",
                    "report_queue",
                    "recovery_runs",
                    "before_image_journal",
                )
            },
            "restored_case_state": snapshot["base_state"],
            "observed_submission_receipts": [
                {
                    "submission_id": row["submission_id"],
                    "case_id": row["case_id"],
                    "channel": row["channel"],
                    "submitted_at_utc": row["submitted_at_utc"],
                    "receipt_id": row["receipt_id"],
                }
                for row in snapshot["submissions"]
            ],
        }
    if write_artifact:
        write_json(ROOT / ".injury_inspect.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def query(sql: str) -> None:
    normalized = sql.strip()
    if not re.match(r"(?is)^select\b", normalized) or ";" in normalized.rstrip(";"):
        raise SystemExit("query accepts exactly one SELECT statement")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        print(
            json.dumps(
                [dict(row) for row in connection.execute(sql)], indent=2, sort_keys=True
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline injury reporting crash-recovery controller"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("sql")
    for name in ("preview", "apply", "stage", "verify", "replay"):
        child = sub.add_parser(name)
        child.add_argument("plan")
    args = parser.parse_args()
    if args.command == "inspect":
        inspect(args.json)
    elif args.command == "query":
        query(args.sql)
    elif args.command == "preview":
        preview(args.plan)
    elif args.command == "apply":
        apply_plan(args.plan)
    elif args.command == "stage":
        stage(args.plan)
    elif args.command == "verify":
        verify(args.plan)
    elif args.command == "replay":
        apply_plan(args.plan, replay_only=True)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        sqlite3.Error,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
