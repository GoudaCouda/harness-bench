#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/lims.db"
PLAN_FIELDS = {
    "schema_version",
    "recovery_id",
    "source_checkpoint",
    "evidence_batch_id",
    "decisions",
    "external_analysis_started",
    "notifications_sent",
}
DECISION_FIELDS = {
    "sample_id",
    "field_label",
    "resolved_lab_label",
    "alias_version",
    "matrix",
    "analysis_suite",
    "receipt_event_id",
    "received_at",
    "receipt_temperature_c",
    "temperature_status",
    "preservation_status",
    "container_status",
    "custody_status",
    "holding_time_status",
    "accession_state",
    "local_mutations",
    "evidence_refs",
    "next_local_action",
    "external_action",
}
MUTABLE_SAMPLE_FIELDS = {
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
EVENT_TYPES = {
    "sample_registered",
    "label_alias",
    "custody_transfer",
    "receipt_observation",
    "late_custody_signature",
}


class CandidateValidationError(ValueError):
    def __init__(self, diagnostics: dict[str, Any]):
        super().__init__("candidate plan did not satisfy the published contract")
        self.diagnostics = diagnostics


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_regular(path: Path, max_bytes: int = 8 * 1024 * 1024) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.relative_to(ROOT)} must be a regular local file")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"{path.relative_to(ROOT)} exceeds the size limit")


def load_json(path: Path) -> dict[str, Any]:
    try:
        safe_regular(path, 1024 * 1024)
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain one JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    if ROOT not in path.parents or path.is_symlink():
        raise ValueError("output must be a regular workspace-local path")
    parent = ROOT
    for part in path.relative_to(ROOT).parts[:-1]:
        parent = parent / part
        if parent.exists() and parent.is_symlink():
            raise ValueError("output parent must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def instant(value: object) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(timezone.utc)


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def source_bundle() -> tuple[dict[str, Any], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source_manifest.json is malformed")
    changed = []
    for locator, expected in files.items():
        path = ROOT / str(locator)
        try:
            safe_regular(path, 1024 * 1024)
            actual = digest(path.read_bytes())
        except (OSError, ValueError):
            actual = "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def verified_events() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trust = load_json(ROOT / "evidence/event_trust.json")
    materials = trust.get("verification_materials")
    if not isinstance(materials, dict):
        raise ValueError("event trust material is malformed")
    try:
        safe_regular(ROOT / "evidence/custody_events.jsonl", 1024 * 1024)
        lines = (ROOT / "evidence/custody_events.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read custody event stream: {exc}") from exc
    unique: dict[str, dict[str, Any]] = {}
    raw_digests: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed custody event line {number}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"custody event line {number} is not an object")
        event_id = str(raw.get("event_id", ""))
        event_type = str(raw.get("event_type", ""))
        key_id = str(raw.get("key_id", ""))
        payload = {key: value for key, value in raw.items() if key not in {"key_id", "signature"}}
        material = materials.get(key_id)
        expected = digest(canonical(payload) + str(material or "").encode())
        if not event_id or event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported or missing event identity on line {number}")
        if material is None or raw.get("signature") != expected:
            raise ValueError(f"event {event_id} failed signature verification")
        raw_hash = digest(canonical(raw))
        if event_id in unique:
            if raw_digests[event_id] != raw_hash:
                raise ValueError(f"conflicting duplicate event_id: {event_id}")
            continue
        instant(raw.get("occurred_at"))
        unique[event_id] = raw
        raw_digests[event_id] = raw_hash
    events = sorted(unique.values(), key=lambda row: (instant(row["occurred_at"]), row["event_id"]))
    return trust, events


def source_baseline(connection: sqlite3.Connection, recovery_id: str) -> tuple[list[dict[str, Any]], int]:
    samples = {row["sample_id"]: row for row in rows(connection, "samples", "sample_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "accession_runs", "recovery_id")}
    journal = rows(connection, "accession_journal", "journal_id")
    current = runs.get(recovery_id)
    if current and current["status"] in {"committed", "staged_pending_review"}:
        for row in journal:
            if row["recovery_id"] == recovery_id:
                samples[row["sample_id"]] = json.loads(row["before_json"])
    for row in journal:
        run = runs.get(row["recovery_id"])
        if run and run["status"] == "interrupted" and not row["restored"]:
            samples[row["sample_id"]] = json.loads(row["before_json"])
    state = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
    revision = int(state.get("source_lims_revision", state.get("lims_revision", "0")))
    return [samples[key] for key in sorted(samples)], revision


def checkpoint_value(
    manifest: dict[str, Any],
    bundle_hash: str,
    source_revision: int,
    baseline: list[dict[str, Any]],
) -> str:
    return digest(
        canonical(
            {
                "immutable_source_hashes": manifest["files"],
                "source_bundle_hash": bundle_hash,
                "source_lims_revision": source_revision,
                "baseline_samples": baseline,
            }
        )
    )


def inspection_contract() -> dict[str, Any]:
    policy = load_json(ROOT / "policy/accession_policy.json")
    manifest, bundle_hash = source_bundle()
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        baseline, source_revision = source_baseline(
            connection, str(policy["recovery_id"])
        )
    return {
        "source_checkpoint": checkpoint_value(
            manifest, bundle_hash, source_revision, baseline
        ),
        "checkpoint_contract": {
            "algorithm": "sha256(canonical-json-with-trailing-newline)",
            "components": [
                "immutable_source_hashes",
                "source_bundle_hash",
                "source_lims_revision",
                "restored_baseline_samples_sorted_by_sample_id",
            ],
            "source_lims_revision": source_revision,
        },
        "decision_vocabulary": policy["decision_vocabulary"],
        "evidence_locator_contract": policy["evidence_locator_contract"],
    }


def all_checks_pass(value: object) -> bool:
    if isinstance(value, dict):
        return all(all_checks_pass(child) for child in value.values())
    return value is True


def _validate_candidate(candidate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    diagnostics: dict[str, Any] = {
        "schema": {
            "exact_top_level": set(candidate) == PLAN_FIELDS,
            "decisions_is_list": isinstance(candidate.get("decisions"), list),
        },
        "identity": {},
        "decisions": {"complete_object_set": False, "objects": {}},
    }
    candidate_rows = candidate.get("decisions")
    if not isinstance(candidate_rows, list):
        candidate_rows = []
    normalized = normalized_plan(candidate)
    actual: dict[str, dict[str, Any]] = {}
    valid_object_rows = 0
    for row in normalized.get("decisions", []):
        if not isinstance(row, dict):
            continue
        valid_object_rows += 1
        sample_id = str(row.get("sample_id", ""))
        actual[sample_id] = row

    policy = load_json(ROOT / "policy/accession_policy.json")
    manifest, bundle_hash = source_bundle()
    _, events = verified_events()
    recovery_id = str(policy["recovery_id"])
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        baseline, source_revision = source_baseline(connection, recovery_id)
    baseline_by_id = {row["sample_id"]: row for row in baseline}
    registered: dict[str, dict[str, Any]] = {}
    aliases: dict[str, list[dict[str, Any]]] = {}
    receipts: dict[str, list[dict[str, Any]]] = {}
    custody: dict[str, list[dict[str, Any]]] = {}
    late: dict[str, list[dict[str, Any]]] = {}
    event_by_id = {row["event_id"]: row for row in events}
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"event {event['event_id']} has malformed payload")
        sample_id = str(payload.get("sample_id", ""))
        event_type = event["event_type"]
        if event_type == "sample_registered":
            if sample_id in registered:
                raise ValueError(f"multiple registrations for {sample_id}")
            registered[sample_id] = event
        elif event_type == "label_alias":
            aliases.setdefault(sample_id, []).append(event)
        elif event_type == "receipt_observation":
            receipts.setdefault(sample_id, []).append(event)
        elif event_type == "custody_transfer":
            custody.setdefault(sample_id, []).append(event)
        else:
            late.setdefault(sample_id, []).append(event)
    if set(registered) != set(baseline_by_id):
        raise ValueError("registered sample identities differ from the protected LIMS baseline")
    suite_rules = policy.get("suite_rules")
    if not isinstance(suite_rules, dict):
        raise ValueError("suite rules are malformed")
    expected_ids: set[str] = set()
    final_samples: dict[str, dict[str, Any]] = {}
    for sample_id in sorted(baseline_by_id):
        original = baseline_by_id[sample_id]
        registration = registered[sample_id]
        reg = registration["payload"]
        protected = {
            "sample_id": sample_id,
            "field_label": original["field_label"],
            "project_id": original["project_id"],
            "client_code": original["client_code"],
            "matrix": original["matrix"],
            "analysis_suite": original["analysis_suite"],
        }
        if any(reg.get(key) != value for key, value in protected.items()):
            raise ValueError(f"registration identity mismatch for {sample_id}")
        alias_events = aliases.get(sample_id, [])
        if not alias_events:
            raise ValueError(f"missing label alias for {sample_id}")
        versions = [int(row["payload"].get("alias_version", -1)) for row in alias_events]
        if len(set(versions)) != len(versions) or min(versions) != 1 or sorted(versions) != list(range(1, max(versions) + 1)):
            raise ValueError(f"broken label alias version chain for {sample_id}")
        chosen_alias = max(alias_events, key=lambda row: int(row["payload"]["alias_version"]))
        if any(row["payload"].get("field_label") != original["field_label"] for row in alias_events):
            raise ValueError(f"alias field-label mismatch for {sample_id}")
        receipt_events = receipts.get(sample_id, [])
        if len(receipt_events) != 1:
            raise ValueError(f"expected one receipt observation for {sample_id}")
        receipt = receipt_events[0]
        observation = receipt["payload"]
        if observation.get("label") != chosen_alias["payload"].get("lab_label"):
            raise ValueError(f"receipt label does not match highest authorized alias for {sample_id}")
        custody_events = custody.get(sample_id, [])
        if len(custody_events) != 1:
            raise ValueError(f"expected one custody transfer for {sample_id}")
        transfer = custody_events[0]
        transfer_payload = transfer["payload"]
        custody_state = "complete"
        custody_refs = [f"evidence/custody_events.jsonl#{transfer['event_id']}"]
        if transfer_payload.get("signature_status") == "pending":
            candidates = [row for row in late.get(sample_id, []) if row["payload"].get("target_event_id") == transfer["event_id"]]
            if len(candidates) != 1:
                custody_state = "missing"
            else:
                signature = candidates[0]
                target_payload_hash = digest(canonical({key: value for key, value in transfer.items() if key not in {"key_id", "signature"}}))
                delay = (instant(signature["occurred_at"]) - instant(transfer["occurred_at"])).total_seconds() / 3600
                if signature["payload"].get("target_checksum") == target_payload_hash and 0 <= delay <= float(policy["late_signature_grace_hours"]):
                    custody_state = "late_signature_valid"
                    custody_refs.append(f"evidence/custody_events.jsonl#{signature['event_id']}")
                else:
                    custody_state = "missing"
        elif transfer_payload.get("signature_status") != "signed":
            custody_state = "missing"
        rule = suite_rules.get(original["analysis_suite"])
        if not isinstance(rule, dict) or rule.get("matrix") != original["matrix"]:
            raise ValueError(f"missing suite/matrix policy for {sample_id}")
        received = instant(observation["received_at"])
        collected = instant(reg["collected_at"])
        elapsed_hours = (received - collected).total_seconds() / 3600
        temperature = float(observation["temperature_c"])
        low, high = [float(value) for value in rule["temperature_c_range"]]
        temperature_state = "within_range" if low <= temperature <= high else "excursion"
        preservation_state = "compliant" if observation.get("preservation") == rule["required_preservation"] else "noncompliant"
        container_state = "intact" if observation.get("container_state") == "intact" and observation.get("container_type") == rule["required_container"] else "damaged"
        holding_state = "within_limit" if 0 <= elapsed_hours <= float(rule["holding_time_hours"]) else "exceeded"
        if container_state == "damaged":
            accession_state, next_action = "rejected_container_integrity", "isolate_for_qa_disposition"
        elif preservation_state != "compliant":
            accession_state, next_action = "rejected_preservation_failure", "isolate_for_qa_disposition"
        elif holding_state != "within_limit":
            accession_state, next_action = "rejected_holding_time", "isolate_for_qa_disposition"
        elif temperature_state != "within_range":
            accession_state, next_action = "quarantine_temperature_excursion", "retain_in_controlled_storage_for_qa"
        elif custody_state == "missing":
            accession_state, next_action = "quarantine_custody_incomplete", "retain_in_controlled_storage_for_qa"
        else:
            accession_state, next_action = "accepted_pending_analysis", "stage_for_qa_accession_review"
        event_ids = sorted({registration["event_id"], chosen_alias["event_id"], transfer["event_id"], receipt["event_id"], *[ref.rsplit("#", 1)[-1] for ref in custody_refs[1:]]})
        event_hash = digest(canonical([event_by_id[event_id] for event_id in event_ids]))
        final = dict(original)
        final.update(
            {
                "resolved_lab_label": chosen_alias["payload"]["lab_label"],
                "alias_version": int(chosen_alias["payload"]["alias_version"]),
                "received_at": observation["received_at"],
                "receipt_temperature_c": temperature,
                "temperature_status": temperature_state,
                "preservation_status": preservation_state,
                "container_status": container_state,
                "custody_status": custody_state,
                "holding_time_status": holding_state,
                "accession_state": accession_state,
                "source_event_digest": event_hash,
                "version": int(original["version"]) + 1,
            }
        )
        changes = sorted(key for key in MUTABLE_SAMPLE_FIELDS if final[key] != original[key])
        refs = [
            f"evidence/custody_events.jsonl#{registration['event_id']}",
            f"evidence/custody_events.jsonl#{chosen_alias['event_id']}",
            *custody_refs,
            f"evidence/custody_events.jsonl#{receipt['event_id']}",
            f"policy/accession_policy.json#suite_rules/{original['analysis_suite']}",
        ]
        expected_row = {
                "sample_id": sample_id,
                "field_label": original["field_label"],
                "resolved_lab_label": chosen_alias["payload"]["lab_label"],
                "alias_version": int(chosen_alias["payload"]["alias_version"]),
                "matrix": original["matrix"],
                "analysis_suite": original["analysis_suite"],
                "receipt_event_id": receipt["event_id"],
                "received_at": observation["received_at"],
                "receipt_temperature_c": temperature,
                "temperature_status": temperature_state,
                "preservation_status": preservation_state,
                "container_status": container_state,
                "custody_status": custody_state,
                "holding_time_status": holding_state,
                "accession_state": accession_state,
                "local_mutations": changes,
                "evidence_refs": sorted(set(refs)),
                "next_local_action": next_action,
                "external_action": "none",
            }
        expected_ids.add(sample_id)
        candidate_row = actual.get(sample_id)
        row_value = candidate_row or {}
        candidate_refs = row_value.get("evidence_refs")
        ref_set = (
            set(candidate_refs)
            if isinstance(candidate_refs, list)
            and all(isinstance(item, str) for item in candidate_refs)
            else set()
        )
        def event_ref(event_id: str) -> str:
            return f"evidence/custody_events.jsonl#{event_id}"
        suite_ref = (
            "policy/accession_policy.json#suite_rules/"
            + str(original["analysis_suite"])
        )
        late_ids = [ref.rsplit("#", 1)[-1] for ref in custody_refs[1:]]
        diagnostics["decisions"]["objects"][sample_id] = {
            "fields": {
                "exact_schema": set(row_value) == DECISION_FIELDS,
                **{
                    key: row_value.get(key) == expected_row[key]
                    for key in sorted(DECISION_FIELDS)
                },
            },
            "evidence_categories": {
                "registration": event_ref(registration["event_id"]) in ref_set,
                "highest_authorized_alias": event_ref(chosen_alias["event_id"])
                in ref_set,
                "custody_transfer": event_ref(transfer["event_id"]) in ref_set,
                "receipt_observation": event_ref(receipt["event_id"]) in ref_set,
                "suite_rule": suite_ref in ref_set,
                "late_custody_signature": (
                    not late_ids
                    or all(event_ref(event_id) in ref_set for event_id in late_ids)
                ),
            },
        }
        final_samples[sample_id] = final
    checkpoint = checkpoint_value(
        manifest, bundle_hash, source_revision, baseline
    )
    diagnostics["decisions"]["complete_object_set"] = (
        valid_object_rows == len(candidate_rows)
        and len(actual) == len(candidate_rows)
        and set(actual) == expected_ids
    )
    diagnostics["identity"] = {
        "schema_version": normalized.get("schema_version") == 1,
        "recovery_id": normalized.get("recovery_id") == policy["recovery_id"],
        "source_checkpoint": normalized.get("source_checkpoint") == checkpoint,
        "evidence_batch_id": normalized.get("evidence_batch_id")
        == policy["evidence_batch_id"],
        "external_analysis_started": normalized.get("external_analysis_started")
        is False,
        "notifications_sent": normalized.get("notifications_sent") is False,
    }
    if not all_checks_pass(diagnostics):
        raise CandidateValidationError(diagnostics)
    return normalized, {
        "policy": policy,
        "events": events,
        "source_checkpoint": checkpoint,
        "source_revision": source_revision,
        "baseline": baseline,
        "final_samples": final_samples,
        "diagnostics": diagnostics,
    }


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    normalized = []
    raw_rows = plan.get("decisions")
    if isinstance(raw_rows, list):
        for raw in raw_rows:
            if not isinstance(raw, dict):
                normalized.append(raw)
                continue
            row = dict(raw)
            for key in ("local_mutations", "evidence_refs"):
                if isinstance(row.get(key), list):
                    row[key] = sorted(row[key])
            normalized.append(row)
    result["decisions"] = sorted(normalized, key=lambda row: str(row.get("sample_id")) if isinstance(row, dict) else "")
    return result


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return _validate_candidate(load_json(path))


def recover_interrupted(connection: sqlite3.Connection) -> list[str]:
    recovered = []
    for run in rows(connection, "accession_runs", "recovery_id"):
        if run["status"] != "interrupted":
            continue
        journal = connection.execute(
            "SELECT journal_id, sample_id, before_json FROM accession_journal WHERE recovery_id=? AND restored=0 ORDER BY journal_id",
            (run["recovery_id"],),
        ).fetchall()
        for journal_id, sample_id, before_json in journal:
            before = json.loads(before_json)
            columns = sorted(before)
            connection.execute(
                f"UPDATE samples SET {', '.join(f'{key}=?' for key in columns)} WHERE sample_id=?",
                [before[key] for key in columns] + [sample_id],
            )
            connection.execute("UPDATE accession_journal SET restored=1 WHERE journal_id=?", (journal_id,))
        connection.execute("UPDATE accession_runs SET status='rolled_back_recovered' WHERE recovery_id=?", (run["recovery_id"],))
        recovered.append(str(run["recovery_id"]))
    return recovered


def preview(plan_path: Path) -> None:
    candidate = load_json(plan_path)
    try:
        plan, facts = _validate_candidate(candidate)
    except CandidateValidationError as exc:
        values = {
            "schema_version": 1,
            "status": "invalid",
            "source_bundle_valid": True,
            "checks": exc.diagnostics,
        }
        write_json(ROOT / ".accession_preview.json", values)
        print(json.dumps(values, indent=2, sort_keys=True))
        raise
    except ValueError as exc:
        values = {
            "schema_version": 1,
            "status": "invalid",
            "source_bundle_valid": False,
            "checks": {},
            "source_error_category": type(exc).__name__,
        }
        write_json(ROOT / ".accession_preview.json", values)
        print(json.dumps(values, indent=2, sort_keys=True))
        raise
    values = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "status": "valid",
        "signed_events_verified": True,
        "duplicate_events_collapsed": 1,
        "decision_count": len(plan["decisions"]),
        "accepted_count": sum(row["accession_state"] == "accepted_pending_analysis" for row in plan["decisions"]),
        "quarantined_count": sum(row["accession_state"].startswith("quarantine_") for row in plan["decisions"]),
        "rejected_count": sum(row["accession_state"].startswith("rejected_") for row in plan["decisions"]),
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": digest(canonical(plan)),
        "external_analysis_started": False,
        "notifications_sent": False,
        "source_bundle_valid": True,
        "checks": facts["diagnostics"],
    }
    write_json(ROOT / ".accession_preview.json", values)
    print(json.dumps(values, indent=2, sort_keys=True))


def apply_plan(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        existing = connection.execute(
            "SELECT status, source_checkpoint, semantic_plan_digest FROM accession_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
        if existing and existing[0] in {"committed", "staged_pending_review"}:
            if existing[1:] == (facts["source_checkpoint"], plan_hash):
                print(json.dumps({"status": "idempotent", "recovery_id": plan["recovery_id"]}))
                return
            raise ValueError("conflict: recovery_id already committed with a different checkpoint or semantic plan")
        connection.execute("BEGIN IMMEDIATE")
        recovered = recover_interrupted(connection)
        for decision in plan["decisions"]:
            sample_id = decision["sample_id"]
            cursor = connection.execute("SELECT * FROM samples WHERE sample_id=?", (sample_id,))
            columns = [item[0] for item in cursor.description]
            before_tuple = cursor.fetchone()
            if before_tuple is None:
                raise ValueError(f"sample disappeared during apply: {sample_id}")
            before = dict(zip(columns, before_tuple, strict=True))
            connection.execute(
                "INSERT INTO accession_journal(recovery_id, sample_id, before_json, restored) VALUES (?, ?, ?, 0)",
                (plan["recovery_id"], sample_id, canonical(before).decode().strip()),
            )
            final = facts["final_samples"][sample_id]
            columns = sorted(final)
            connection.execute(
                f"UPDATE samples SET {', '.join(f'{key}=?' for key in columns)} WHERE sample_id=?",
                [final[key] for key in columns] + [sample_id],
            )
        revision = facts["source_revision"] + 1
        connection.execute(
            "INSERT INTO accession_runs VALUES (?, 'committed', ?, ?, '', ?, 0, 0, 0, 0)",
            (plan["recovery_id"], facts["source_checkpoint"], plan_hash, revision),
        )
        connection.execute("UPDATE system_state SET value=? WHERE key='lims_revision'", (str(revision),))
        connection.execute("UPDATE system_state SET value='committed_local_accession' WHERE key='stage_state'")
        logical_hash = digest(canonical({"samples": rows(connection, "samples", "sample_id")}))
        connection.execute("UPDATE accession_runs SET semantic_db_digest=? WHERE recovery_id=?", (logical_hash, plan["recovery_id"]))
        connection.commit()
    print(json.dumps({"status": "committed", "recovered_runs": recovered, "recovery_id": plan["recovery_id"]}))


def expected_closure(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        sample_rows = rows(connection, "samples", "sample_id")
    db_hash = digest(canonical({"samples": sample_rows}))
    verification = {
        "schema_version": 1,
        "recovery_id": plan["recovery_id"],
        "status": "pass",
        "checks": {
            "source_checkpoint_matches": True,
            "semantic_plan_matches": True,
            "sample_master_exact": True,
            "interrupted_journal_recovered": True,
            "single_committed_recovery": True,
            "analysis_not_started": True,
            "results_not_released": True,
            "local_only": True,
        },
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_db_digest": db_hash,
        "final_revision": facts["source_revision"] + 1,
        "external_analysis_started": False,
        "notifications_sent": False,
    }
    return verification, facts, plan_hash, db_hash


def verify(plan_path: Path) -> None:
    verification, facts, plan_hash, db_hash = expected_closure(plan_path)
    with sqlite3.connect(DB) as connection:
        samples = {row["sample_id"]: row for row in rows(connection, "samples", "sample_id")}
        runs = {row["recovery_id"]: row for row in rows(connection, "accession_runs", "recovery_id")}
        journal = rows(connection, "accession_journal", "journal_id")
        state = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
    problems = []
    for sample_id, target in facts["final_samples"].items():
        if samples.get(sample_id) != target:
            problems.append(f"sample master differs for {sample_id}")
        current = samples.get(sample_id, {})
        if current.get("analysis_started") or current.get("results_released") or current.get("notification_state") != "none":
            problems.append(f"external boundary changed for {sample_id}")
    current = runs.get(str(facts["policy"]["recovery_id"]), {})
    if current.get("status") not in {"committed", "staged_pending_review"}:
        problems.append("current recovery is not committed")
    if current.get("source_checkpoint") != facts["source_checkpoint"] or current.get("semantic_plan_digest") != plan_hash or current.get("semantic_db_digest") != db_hash:
        problems.append("recovery hashes do not close")
    if any(row["status"] == "interrupted" for row in runs.values()) or any(not row["restored"] for row in journal if row["recovery_id"] != facts["policy"]["recovery_id"]):
        problems.append("interrupted journal was not recovered")
    if state.get("lims_revision") != str(facts["source_revision"] + 1):
        problems.append("LIMS revision differs")
    if problems:
        raise ValueError("verification failed:\n- " + "\n- ".join(problems))
    write_json(ROOT / "state/verification.json", verification)
    print(json.dumps(verification, indent=2, sort_keys=True))


def stage(plan_path: Path) -> None:
    verification, facts, plan_hash, db_hash = expected_closure(plan_path)
    saved = load_json(ROOT / "state/verification.json")
    if saved != verification:
        raise ValueError("run verify before stage; verification artifact is missing or stale")
    verification_hash = digest(canonical(verification))
    token_input = {
        "recovery_id": facts["policy"]["recovery_id"],
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_db_digest": db_hash,
        "verification_hash": verification_hash,
        "stage_boundary": "local_only_pending_accession_qa_review",
    }
    receipt = {
        "schema_version": 1,
        **token_input,
        "status": "staged_pending_review",
        "stage_token": digest(canonical(token_input)),
        "external_analysis_started": False,
        "notifications_sent": False,
    }
    write_json(ROOT / "state/recovery_receipt.json", receipt)
    with sqlite3.connect(DB) as connection:
        status = connection.execute("SELECT status FROM accession_runs WHERE recovery_id=?", (facts["policy"]["recovery_id"],)).fetchone()
        stage_state = connection.execute("SELECT value FROM system_state WHERE key='stage_state'").fetchone()
        if status != ("staged_pending_review",) or stage_state != ("staged_pending_review",):
            connection.execute("UPDATE accession_runs SET status='staged_pending_review' WHERE recovery_id=?", (facts["policy"]["recovery_id"],))
            connection.execute("UPDATE system_state SET value='staged_pending_review' WHERE key='stage_state'")
            connection.commit()
    print(json.dumps(receipt, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    db_before = DB.read_bytes()
    receipt_path = ROOT / "state/recovery_receipt.json"
    receipt_before = receipt_path.read_bytes()
    apply_plan(plan_path)
    verify(plan_path)
    stage(plan_path)
    report = {
        "schema_version": 1,
        "recovery_id": load_json(plan_path)["recovery_id"],
        "status": "pass",
        "database_byte_stable": DB.read_bytes() == db_before,
        "receipt_byte_stable": receipt_path.read_bytes() == receipt_before,
        "single_committed_recovery": True,
        "external_analysis_started": False,
        "notifications_sent": False,
    }
    if not report["database_byte_stable"] or not report["receipt_byte_stable"]:
        raise ValueError("replay changed the committed database or receipt")
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def inspect(as_json: bool) -> None:
    policy = load_json(ROOT / "policy/accession_policy.json")
    contract = inspection_contract()
    try:
        _, events = verified_events()
        event_summary: object = {
            "unique_verified": len(events),
            "stream_lines": len((ROOT / "evidence/custody_events.jsonl").read_text(encoding="utf-8").splitlines()),
            "types": {kind: sum(row["event_type"] == kind for row in events) for kind in sorted(EVENT_TYPES)},
        }
    except ValueError as exc:
        event_summary = {"error": str(exc)}
    with sqlite3.connect(DB) as connection:
        output = {
            "policy": policy,
            "event_stream": event_summary,
            "samples": rows(connection, "samples", "sample_id"),
            "runs": rows(connection, "accession_runs", "recovery_id"),
            "journal": rows(connection, "accession_journal", "journal_id"),
            "system_state": rows(connection, "system_state", "key"),
            "contract": contract,
        }
    if as_json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"recovery_id: {policy['recovery_id']}")
        print(f"evidence_batch_id: {policy['evidence_batch_id']}")
        print(f"source_checkpoint: {contract['source_checkpoint']}")
        print("checkpoint_contract: " + json.dumps(contract["checkpoint_contract"], sort_keys=True))
        print("decision_vocabulary: " + json.dumps(contract["decision_vocabulary"], sort_keys=True))
        print("evidence_locator_contract: " + json.dumps(contract["evidence_locator_contract"], sort_keys=True))
        print("event_stream: " + json.dumps(event_summary, sort_keys=True))
        for row in output["samples"]:
            print("sample: " + json.dumps(row, sort_keys=True))
        for row in output["runs"]:
            print("run: " + json.dumps(row, sort_keys=True))
        for row in output["journal"]:
            print("journal: " + json.dumps(row, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded offline environmental-LIMS accession recovery")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("plan")
    arguments = parser.parse_args()
    try:
        if arguments.command == "inspect":
            inspect(arguments.json)
        else:
            plan_path = (ROOT / arguments.plan).resolve()
            if ROOT not in plan_path.parents or plan_path.parent != ROOT:
                raise ValueError("plan must be a regular top-level workspace file")
            if not plan_path.is_file() or plan_path.is_symlink():
                raise ValueError("plan must be a regular file")
            {"preview": preview, "apply": apply_plan, "verify": verify, "stage": stage, "replay": replay}[arguments.command](plan_path)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
