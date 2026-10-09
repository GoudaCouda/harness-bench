#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/vendor_master.db"
PLAN_FIELDS = {
    "schema_version",
    "renewal_id",
    "source_checkpoint",
    "registry_snapshot_id",
    "decisions",
    "external_actions_executed",
    "bank_information_collected",
}
DECISION_FIELDS = {
    "vendor_id",
    "registry_entity_id",
    "legal_name",
    "registry_version",
    "legal_name_version",
    "legal_name_effective_date",
    "registration_status",
    "registration_expires_on",
    "beneficial_owner_requirement",
    "beneficial_owner_attestation_status",
    "compliance_state",
    "renewal_state",
    "local_mutations",
    "evidence_refs",
    "next_local_action",
    "external_action",
}
MUTABLE_VENDOR_FIELDS = {
    "legal_name",
    "registry_version",
    "registry_effective_date",
    "registration_status",
    "registration_expires_on",
    "beneficial_owner_attestation_status",
    "compliance_state",
    "renewal_state",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain one JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iso_date(value: object) -> date:
    return date.fromisoformat(str(value))


def table_rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
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
            actual = digest(path.read_bytes())
        except OSError:
            actual = "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return manifest, digest(canonical(files))


def trusted_sources() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trust = load_json(ROOT / "evidence/registry_trust.json")
    raw = load_json(ROOT / "evidence/registry_snapshot.json")
    signature = str(raw.get("signature", ""))
    key_id = str(raw.get("key_id", ""))
    payload = {key: value for key, value in raw.items() if key not in {"signature", "key_id"}}
    expected = digest(canonical(payload) + str(trust.get("registry_verification_material", "")).encode())
    if key_id != trust.get("registry_key_id") or signature != expected:
        raise ValueError("registry snapshot signature verification failed")
    corrections: list[dict[str, Any]] = []
    try:
        lines = (ROOT / "evidence/legal_name_corrections.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read legal-name corrections: {exc}") from exc
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed legal-name correction line {number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"legal-name correction line {number} is not an object")
        row_signature = str(row.get("signature", ""))
        row_key = str(row.get("key_id", ""))
        row_payload = {key: value for key, value in row.items() if key not in {"signature", "key_id"}}
        row_expected = digest(canonical(row_payload) + str(trust.get("correction_verification_material", "")).encode())
        if row_key != trust.get("correction_key_id") or row_signature != row_expected:
            raise ValueError(f"legal-name correction line {number} failed signature verification")
        corrections.append(row)
    payload["signature"] = signature
    payload["key_id"] = key_id
    return payload, corrections


def primary_is_truncated() -> bool:
    path = ROOT / "evidence/primary_registry_export.json.part"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return True
    return False


def source_baseline(connection: sqlite3.Connection, renewal_id: str) -> tuple[list[dict[str, Any]], int]:
    vendors = {row["vendor_id"]: row for row in table_rows(connection, "vendors", "vendor_id")}
    runs = {row["renewal_id"]: row for row in table_rows(connection, "renewal_runs", "renewal_id")}
    journal = table_rows(connection, "renewal_journal", "journal_id")
    current = runs.get(renewal_id)
    if current and current["status"] in {"committed", "staged_pending_review"}:
        for row in journal:
            if row["renewal_id"] == renewal_id:
                vendors[row["vendor_id"]] = json.loads(row["before_json"])
    for row in journal:
        run = runs.get(row["renewal_id"])
        if run and run["status"] == "interrupted" and not row["restored"]:
            vendors[row["vendor_id"]] = json.loads(row["before_json"])
    state = dict(
        connection.execute("SELECT key, value FROM system_state").fetchall()
    )
    revision = int(state.get("source_master_revision", state.get("master_revision", "0")))
    return [vendors[key] for key in sorted(vendors)], revision


def owner_required(policy: dict[str, Any], vendor: dict[str, Any]) -> bool:
    rule = policy["beneficial_owner_rule"]
    return (
        vendor["entity_type"] in set(rule["required_entity_types"])
        and vendor["risk_tier"] in set(rule["required_risk_tiers"])
    )


def owner_status(policy: dict[str, Any], record: dict[str, Any], required: bool) -> str:
    if not required:
        return "not_required"
    item = record.get("beneficial_owner_attestation")
    if not isinstance(item, dict):
        return "missing"
    if set(item) != set(policy["beneficial_owner_rule"]["minimum_fields"]):
        raise ValueError("registry owner attestation violates the minimum-field schema")
    as_of = iso_date(policy["as_of"])
    if (
        item.get("status") == "verified"
        and iso_date(item["effective_date"]) <= as_of <= iso_date(item["expires_on"])
        and isinstance(item.get("owner_count"), int)
        and item["owner_count"] >= 0
    ):
        return "current"
    return "missing"


def renewal_inputs() -> dict[str, Any]:
    """Return verified source facts only, never the completed candidate plan."""
    policy = load_json(ROOT / "policy/renewal_policy.json")
    manifest, source_bundle_hash = source_bundle()
    if not primary_is_truncated():
        raise ValueError("primary export is parseable; signed fallback is not authorized")
    snapshot, corrections = trusted_sources()
    with sqlite3.connect(DB) as connection:
        baseline, source_revision = source_baseline(connection, str(policy["renewal_id"]))
    baseline_by_id = {row["vendor_id"]: row for row in baseline}
    registry_records = snapshot.get("records")
    if not isinstance(registry_records, list):
        raise ValueError("registry snapshot records are malformed")
    registry_by_entity = {
        str(row["registry_entity_id"]): row
        for row in registry_records
        if isinstance(row, dict)
    }
    checkpoint_payload = {
        "immutable_source_hashes": manifest["files"],
        "source_bundle_hash": source_bundle_hash,
        "source_master_revision": source_revision,
        "baseline_vendors": baseline,
    }
    return {
        "policy": policy,
        "snapshot": snapshot,
        "corrections": corrections,
        "source_bundle_hash": source_bundle_hash,
        "source_checkpoint": digest(canonical(checkpoint_payload)),
        "source_revision": source_revision,
        "baseline": baseline,
        "baseline_by_id": baseline_by_id,
        "registry_by_entity": registry_by_entity,
    }


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    decisions = []
    rows = plan.get("decisions")
    if isinstance(rows, list):
        for raw in rows:
            if not isinstance(raw, dict):
                decisions.append(raw)
                continue
            row = dict(raw)
            for key in ("local_mutations", "evidence_refs"):
                if isinstance(row.get(key), list):
                    row[key] = sorted(set(str(item) for item in row[key]))
            decisions.append(row)
        result["decisions"] = sorted(decisions, key=lambda row: str(row.get("vendor_id")) if isinstance(row, dict) else "")
    return result


def has_local_locator(refs: list[str], filename: str, object_id: str) -> bool:
    return any(
        ref.startswith(filename)
        and (ref.endswith(f"#{object_id}") or ref.endswith(f"/{object_id}"))
        for ref in refs
    )


def validate_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = normalized_plan(load_json(path))
    facts = renewal_inputs()
    policy = facts["policy"]
    snapshot = facts["snapshot"]
    corrections = facts["corrections"]
    baseline_by_id = facts["baseline_by_id"]
    registry_by_entity = facts["registry_by_entity"]
    problems: list[str] = []
    if set(candidate) != PLAN_FIELDS:
        problems.append(f"top-level fields must be exactly {sorted(PLAN_FIELDS)}")
    if candidate.get("schema_version") != 1 or candidate.get("renewal_id") != policy["renewal_id"]:
        problems.append("schema_version or renewal_id violates the published policy")
    if candidate.get("source_checkpoint") != facts["source_checkpoint"]:
        problems.append("source_checkpoint differs from protected sources and restored baseline")
    if candidate.get("registry_snapshot_id") != snapshot["snapshot_id"]:
        problems.append("registry_snapshot_id differs from the verified snapshot")
    if candidate.get("external_actions_executed") is not False:
        problems.append("external_actions_executed must be false")
    if candidate.get("bank_information_collected") is not False:
        problems.append("bank_information_collected must be false")
    rows = candidate.get("decisions")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != DECISION_FIELDS for row in rows):
        problems.append(f"every decision must have exactly {sorted(DECISION_FIELDS)}")
        rows = []
    got = {str(row.get("vendor_id")): row for row in rows if isinstance(row, dict)}
    cutoff = iso_date(policy["as_of"]) + timedelta(days=int(policy["renewal_window_days"]))
    in_window: set[str] = set()
    for vendor_id in sorted(baseline_by_id):
        baseline_row = baseline_by_id[vendor_id]
        registry = registry_by_entity.get(str(baseline_row["registry_entity_id"]))
        if not registry:
            raise ValueError(f"vendor {vendor_id} lacks a registry record")
        expires = iso_date(registry["registration_expires_on"])
        if expires > cutoff and registry["registration_status"] == "active":
            continue
        in_window.add(vendor_id)
        legal_name = str(registry["legal_name"])
        legal_version = int(registry["version"])
        legal_effective = str(registry["effective_date"])
        correction_ref = None
        candidates = []
        for row in corrections:
            if row.get("vendor_id") != vendor_id:
                continue
            if row.get("previous_legal_name") != registry["legal_name"]:
                raise ValueError(f"correction chain mismatch for {vendor_id}")
            if int(row["version"]) <= int(registry["version"]):
                raise ValueError(f"correction version is not newer for {vendor_id}")
            if iso_date(row["effective_date"]) <= iso_date(policy["as_of"]):
                candidates.append(row)
        if candidates:
            chosen = max(candidates, key=lambda row: (int(row["version"]), str(row["effective_date"])))
            legal_name = str(chosen["legal_name"])
            legal_version = int(chosen["version"])
            legal_effective = str(chosen["effective_date"])
            correction_ref = f"evidence/legal_name_corrections.jsonl#{chosen['correction_id']}"
        required = owner_required(policy, baseline_row)
        attestation = owner_status(policy, registry, required)
        active_registration = (
            registry["registration_status"] == "active"
            and expires >= iso_date(policy["as_of"])
        )
        if not active_registration:
            compliance, renewal, next_action = (
                "registration_expired",
                "pending_external_registry_renewal",
                "request_registry_renewal_evidence",
            )
        elif required and attestation != "current":
            compliance, renewal, next_action = (
                "owner_attestation_required",
                "hold_owner_attestation",
                "request_minimum_owner_attestation",
            )
        else:
            compliance, renewal, next_action = (
                "compliant_for_review",
                "ready_for_internal_approval",
                "route_for_internal_approval",
            )
        final = dict(baseline_row)
        final.update({"legal_name": legal_name, "registry_version": int(registry["version"]), "registry_effective_date": str(registry["effective_date"]), "registration_status": str(registry["registration_status"]), "registration_expires_on": str(registry["registration_expires_on"]), "beneficial_owner_attestation_status": attestation, "compliance_state": compliance, "renewal_state": renewal, "activation_state": baseline_row["activation_state"], "version": int(baseline_row["version"]) + 1})
        changes = sorted(
            key for key in MUTABLE_VENDOR_FIELDS if final[key] != baseline_row[key]
        )
        evidence_refs = [
            f"evidence/registry_snapshot.json#{registry['registry_entity_id']}",
            "policy/renewal_policy.json#beneficial_owner_rule",
        ]
        if correction_ref:
            evidence_refs.append(correction_ref)
        required = {
                "vendor_id": vendor_id,
                "registry_entity_id": str(registry["registry_entity_id"]),
                "legal_name": legal_name,
                "registry_version": int(registry["version"]),
                "legal_name_version": legal_version,
                "legal_name_effective_date": legal_effective,
                "registration_status": str(registry["registration_status"]),
                "registration_expires_on": str(registry["registration_expires_on"]),
                "beneficial_owner_requirement": "required" if required else "not_required",
                "beneficial_owner_attestation_status": attestation,
                "compliance_state": compliance,
                "renewal_state": renewal,
                "local_mutations": changes,
                "evidence_refs": sorted(evidence_refs),
                "next_local_action": next_action,
                "external_action": "none",
        }
        row = got.get(vendor_id)
        differing = sorted(
            key for key in DECISION_FIELDS
            if key != "evidence_refs"
            and (not isinstance(row, dict) or row.get(key) != required[key])
        )
        if differing:
            problems.append(f"{vendor_id} differs in: {', '.join(differing)}")
        if isinstance(row, dict):
            refs = row.get("evidence_refs", [])
            missing = []
            if not has_local_locator(refs, "evidence/registry_snapshot.json", str(registry["registry_entity_id"])):
                missing.append("signed registry entity")
            if correction_ref and not has_local_locator(refs, "evidence/legal_name_corrections.jsonl", str(correction_ref).rsplit("#", 1)[-1]):
                missing.append("effective legal-name correction")
            if not has_local_locator(
                refs,
                "policy/renewal_policy.json",
                "beneficial_owner_rule",
            ):
                missing.append("beneficial-owner policy")
            if missing:
                problems.append(f"{vendor_id} is missing evidence categories: {', '.join(missing)}")
    if set(got) != in_window:
        problems.append("decision vendor set differs from the renewal window")
    if problems:
        raise ValueError("plan validation failed:\n- " + "\n- ".join(problems))
    return candidate, facts


def logical_db(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "vendors": table_rows(connection, "vendors", "vendor_id"),
        "renewal_runs": table_rows(connection, "renewal_runs", "renewal_id"),
        "renewal_journal": table_rows(connection, "renewal_journal", "journal_id"),
        "system_state": table_rows(connection, "system_state", "key"),
    }


def recover_interrupted(connection: sqlite3.Connection) -> list[str]:
    recovered = []
    runs = table_rows(connection, "renewal_runs", "renewal_id")
    for run in runs:
        if run["status"] != "interrupted":
            continue
        rows = connection.execute(
            "SELECT journal_id, vendor_id, before_json FROM renewal_journal WHERE renewal_id=? AND restored=0 ORDER BY journal_id",
            (run["renewal_id"],),
        ).fetchall()
        for journal_id, vendor_id, before_json in rows:
            before = json.loads(before_json)
            columns = sorted(before)
            assignments = ", ".join(f"{key}=?" for key in columns)
            connection.execute(
                f"UPDATE vendors SET {assignments} WHERE vendor_id=?",
                [before[key] for key in columns] + [vendor_id],
            )
            connection.execute(
                "UPDATE renewal_journal SET restored=1 WHERE journal_id=?", (journal_id,)
            )
        connection.execute(
            "UPDATE renewal_runs SET status='rolled_back_recovered' WHERE renewal_id=?",
            (run["renewal_id"],),
        )
        recovered.append(str(run["renewal_id"]))
    return recovered


def projected_vendor(facts: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Project one already-validated candidate decision onto its baseline row."""
    baseline = dict(facts["baseline_by_id"][decision["vendor_id"]])
    registry = facts["registry_by_entity"][decision["registry_entity_id"]]
    baseline.update(
        {
            "legal_name": decision["legal_name"],
            "registry_version": decision["registry_version"],
            "registry_effective_date": str(registry["effective_date"]),
            "registration_status": decision["registration_status"],
            "registration_expires_on": decision["registration_expires_on"],
            "beneficial_owner_attestation_status": decision["beneficial_owner_attestation_status"],
            "compliance_state": decision["compliance_state"],
            "renewal_state": decision["renewal_state"],
            "version": int(baseline["version"]) + 1,
        }
    )
    return baseline


def preview(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    values = {
        "schema_version": 1,
        "renewal_id": plan["renewal_id"],
        "status": "valid",
        "primary_export_rejected_as_truncated": True,
        "registry_signature_verified": True,
        "correction_signatures_verified": True,
        "decision_count": len(plan["decisions"]),
        "ready_count": sum(row["renewal_state"] == "ready_for_internal_approval" for row in plan["decisions"]),
        "held_count": sum(row["renewal_state"] == "hold_owner_attestation" for row in plan["decisions"]),
        "pending_registry_count": sum(row["renewal_state"] == "pending_external_registry_renewal" for row in plan["decisions"]),
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": digest(canonical(plan)),
        "external_actions_executed": False,
        "bank_information_collected": False,
    }
    write_json(ROOT / ".renewal_preview.json", values)
    print(json.dumps(values, indent=2, sort_keys=True))


def apply(plan_path: Path) -> None:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        existing = connection.execute(
            "SELECT status, source_checkpoint, semantic_plan_digest FROM renewal_runs WHERE renewal_id=?",
            (plan["renewal_id"],),
        ).fetchone()
        if existing and existing[0] in {"committed", "staged_pending_review"}:
            if existing[1:] == (facts["source_checkpoint"], plan_hash):
                print(json.dumps({"status": "idempotent", "renewal_id": plan["renewal_id"]}))
                return
            raise ValueError("conflict: renewal_id already committed with a different checkpoint or semantic plan")
        connection.execute("BEGIN IMMEDIATE")
        recovered = recover_interrupted(connection)
        for decision in plan["decisions"]:
            vendor_id = decision["vendor_id"]
            before_cursor = connection.execute("SELECT * FROM vendors WHERE vendor_id=?", (vendor_id,))
            columns = [item[0] for item in before_cursor.description]
            before_tuple = before_cursor.fetchone()
            if before_tuple is None:
                raise ValueError(f"vendor disappeared during apply: {vendor_id}")
            before = dict(zip(columns, before_tuple, strict=True))
            connection.execute(
                "INSERT INTO renewal_journal(renewal_id, vendor_id, before_json, restored) VALUES (?, ?, ?, 0)",
                (plan["renewal_id"], vendor_id, canonical(before).decode().strip()),
            )
            final = projected_vendor(facts, decision)
            assignments = ", ".join(f"{key}=?" for key in sorted(final))
            connection.execute(
                f"UPDATE vendors SET {assignments} WHERE vendor_id=?",
                [final[key] for key in sorted(final)] + [vendor_id],
            )
        final_revision = facts["source_revision"] + 1
        connection.execute(
            "INSERT INTO renewal_runs(renewal_id, status, source_checkpoint, semantic_plan_digest, semantic_db_digest, final_revision, external_actions_executed, bank_information_collected) VALUES (?, 'committed', ?, ?, '', ?, 0, 0)",
            (plan["renewal_id"], facts["source_checkpoint"], plan_hash, final_revision),
        )
        connection.execute("UPDATE system_state SET value=? WHERE key='master_revision'", (str(final_revision),))
        connection.execute("UPDATE system_state SET value='committed_local_review' WHERE key='stage_state'")
        logical_hash = digest(canonical({"vendors": table_rows(connection, "vendors", "vendor_id")}))
        connection.execute(
            "UPDATE renewal_runs SET semantic_db_digest=? WHERE renewal_id=?",
            (logical_hash, plan["renewal_id"]),
        )
        connection.commit()
    print(json.dumps({"status": "committed", "recovered_runs": recovered, "renewal_id": plan["renewal_id"]}))


def expected_closure(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    plan, facts = validate_plan(plan_path)
    plan_hash = digest(canonical(plan))
    with sqlite3.connect(DB) as connection:
        vendors = table_rows(connection, "vendors", "vendor_id")
    db_hash = digest(canonical({"vendors": vendors}))
    verification = {
        "schema_version": 1,
        "renewal_id": plan["renewal_id"],
        "status": "pass",
        "checks": {
            "source_checkpoint_matches": True,
            "semantic_plan_matches": True,
            "vendor_master_exact": True,
            "interrupted_journal_recovered": True,
            "single_committed_recovery": True,
            "vendors_not_activated": True,
            "minimum_owner_data_only": True,
            "local_only": True,
        },
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_db_digest": db_hash,
        "final_revision": facts["source_revision"] + 1,
        "external_actions_executed": False,
        "bank_information_collected": False,
    }
    return verification, facts, plan_hash, db_hash


def verify(plan_path: Path) -> None:
    verification, facts, plan_hash, db_hash = expected_closure(plan_path)
    verification_plan = normalized_plan(load_json(plan_path))
    with sqlite3.connect(DB) as connection:
        vendors = {row["vendor_id"]: row for row in table_rows(connection, "vendors", "vendor_id")}
        runs = {row["renewal_id"]: row for row in table_rows(connection, "renewal_runs", "renewal_id")}
        journal = table_rows(connection, "renewal_journal", "journal_id")
        state = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
    problems = []
    for decision in verification_plan["decisions"]:
        vendor_id = decision["vendor_id"]
        target = projected_vendor(facts, decision)
        if vendors.get(vendor_id) != target:
            problems.append(f"vendor master differs for {vendor_id}")
        if vendors.get(vendor_id, {}).get("activation_state") != next(row["activation_state"] for row in facts["baseline"] if row["vendor_id"] == vendor_id):
            problems.append(f"activation state changed for {vendor_id}")
    run = runs.get(str(facts["policy"]["renewal_id"]), {})
    if run.get("status") not in {"committed", "staged_pending_review"}:
        problems.append("current recovery is not committed")
    if run.get("source_checkpoint") != facts["source_checkpoint"] or run.get("semantic_plan_digest") != plan_hash or run.get("semantic_db_digest") != db_hash:
        problems.append("run hashes do not close")
    if sum(row["renewal_id"] == facts["policy"]["renewal_id"] for row in runs.values()) != 1:
        problems.append("renewal transaction is not unique")
    if any(row["status"] == "interrupted" for row in runs.values()) or any(not row["restored"] for row in journal if row["renewal_id"] != facts["policy"]["renewal_id"]):
        problems.append("interrupted journal was not recovered")
    if state.get("master_revision") != str(facts["source_revision"] + 1):
        problems.append("master revision differs")
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
        "renewal_id": facts["policy"]["renewal_id"],
        "source_checkpoint": facts["source_checkpoint"],
        "semantic_plan_digest": plan_hash,
        "semantic_db_digest": db_hash,
        "verification_hash": verification_hash,
        "stage_boundary": "local_only_pending_vendor_compliance_review",
    }
    receipt = {
        "schema_version": 1,
        **token_input,
        "status": "staged_pending_review",
        "stage_token": digest(canonical(token_input)),
        "external_actions_executed": False,
        "bank_information_collected": False,
    }
    write_json(ROOT / "state/recovery_receipt.json", receipt)
    with sqlite3.connect(DB) as connection:
        status = connection.execute(
            "SELECT status FROM renewal_runs WHERE renewal_id=?",
            (facts["policy"]["renewal_id"],),
        ).fetchone()
        stage_state = connection.execute(
            "SELECT value FROM system_state WHERE key='stage_state'"
        ).fetchone()
        if status != ("staged_pending_review",) or stage_state != ("staged_pending_review",):
            connection.execute(
                "UPDATE renewal_runs SET status='staged_pending_review' WHERE renewal_id=?",
                (facts["policy"]["renewal_id"],),
            )
            connection.execute(
                "UPDATE system_state SET value='staged_pending_review' WHERE key='stage_state'"
            )
            connection.commit()
    print(json.dumps(receipt, indent=2, sort_keys=True))


def replay(plan_path: Path) -> None:
    db_before = DB.read_bytes()
    receipt_path = ROOT / "state/recovery_receipt.json"
    receipt_before = receipt_path.read_bytes()
    apply(plan_path)
    verify(plan_path)
    stage(plan_path)
    report = {
        "schema_version": 1,
        "renewal_id": load_json(plan_path)["renewal_id"],
        "status": "pass",
        "database_byte_stable": DB.read_bytes() == db_before,
        "receipt_byte_stable": receipt_path.read_bytes() == receipt_before,
        "single_committed_recovery": True,
        "external_actions_executed": False,
        "bank_information_collected": False,
    }
    if not report["database_byte_stable"] or not report["receipt_byte_stable"]:
        raise ValueError("replay changed the committed database or receipt")
    write_json(ROOT / "state/replay_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def contract() -> None:
    """Publish candidate schema and controlled vocabularies, never decisions."""
    policy = load_json(ROOT / "policy/renewal_policy.json")
    result = {
        "schema_version": 1,
        "top_level_fields": sorted(PLAN_FIELDS),
        "decision_fields": sorted(DECISION_FIELDS),
        "set_fields": ["evidence_refs", "local_mutations"],
        "vocabularies": {
            "beneficial_owner_requirement": ["not_required", "required"],
            "beneficial_owner_attestation_status": [
                "current",
                "missing",
                "not_required",
            ],
            "compliance_state": sorted(policy["compliance_states"]),
            "renewal_state": sorted(policy["renewal_states"]),
            "next_local_action": [
                "request_minimum_owner_attestation",
                "request_registry_renewal_evidence",
                "route_for_internal_approval",
            ],
            "external_action": ["none"],
            "local_mutations": sorted(MUTABLE_VENDOR_FIELDS),
        },
        "evidence_requirements": [
            "signed_registry_entity",
            "beneficial_owner_policy",
            "effective_legal_name_correction_if_applicable",
        ],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def inspect(as_json: bool) -> None:
    policy = load_json(ROOT / "policy/renewal_policy.json")
    try:
        facts = renewal_inputs()
        snapshot = facts["snapshot"]
        corrections = facts["corrections"]
        verified = True
        snapshot_id = snapshot.get("snapshot_id")
        source_checkpoint = facts["source_checkpoint"]
    except ValueError:
        verified, snapshot_id, source_checkpoint, corrections = False, None, None, []
    with sqlite3.connect(DB) as connection:
        vendors = table_rows(connection, "vendors", "vendor_id")
        runs = table_rows(connection, "renewal_runs", "renewal_id")
        state = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
    result = {
        "renewal_id": policy.get("renewal_id"),
        "as_of": policy.get("as_of"),
        "primary_export_truncated": primary_is_truncated(),
        "registry_snapshot_verified": verified,
        "registry_snapshot_id": snapshot_id,
        "source_checkpoint": source_checkpoint,
        "signed_correction_count": len(corrections),
        "vendor_count": len(vendors),
        "vendors": [
            {key: row[key] for key in ("vendor_id", "registry_entity_id", "legal_name", "entity_type", "risk_tier", "activation_state", "version")}
            for row in vendors
        ],
        "runs": [{"renewal_id": row["renewal_id"], "status": row["status"]} for row in runs],
        "system_state": state,
    }
    print(json.dumps(result, indent=2, sort_keys=True) if as_json else "\n".join(f"{key}: {value}" for key, value in result.items()))


def query(table: str) -> None:
    allowed = {"vendors": "vendor_id", "renewal_runs": "renewal_id", "renewal_journal": "journal_id", "system_state": "key"}
    if table not in allowed:
        raise ValueError("query table must be one of: " + ", ".join(sorted(allowed)))
    with sqlite3.connect(DB) as connection:
        print(json.dumps(table_rows(connection, table, allowed[table]), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarded offline vendor-renewal recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("contract")
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("table")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("plan")
    args = parser.parse_args()
    if args.command == "contract":
        contract()
    elif args.command == "inspect":
        inspect(args.json)
    elif args.command == "query":
        query(args.table)
    else:
        globals()[args.command]((ROOT / args.plan).resolve())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
