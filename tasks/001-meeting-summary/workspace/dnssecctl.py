#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/dnssec.db"
POLICY = ROOT / "policy/rollover_policy.json"
MANIFEST = ROOT / "policy/source_manifest.json"
INVENTORY = ROOT / "evidence/key_inventory.json"
PARENT = ROOT / "evidence/parent_ds_observations.jsonl"
DNS = ROOT / "evidence/dns_observations.jsonl"
CHECKPOINT = ROOT / "state/stale_checkpoint.json"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def read_rows(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{number} must contain an object")
        values.append(value)
    return values


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def table(connection: sqlite3.Connection, name: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {name} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def database_state(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "zones": table(connection, "zones", "zone_name"),
        "keys": table(connection, "key_state", "key_id"),
        "queue": table(connection, "staging_queue", "queue_id"),
        "receipts": table(connection, "decision_receipts", "recovery_id,zone_name"),
        "runs": table(connection, "recovery_runs", "recovery_id"),
        "journal": table(connection, "rollover_journal", "journal_id"),
        "system": dict(connection.execute("SELECT key,value FROM system_state")),
    }


def recovered_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    zones = {row["zone_name"]: dict(row) for row in snapshot["zones"]}
    queue = {row["queue_id"]: dict(row) for row in snapshot["queue"]}
    interrupted = {
        row["recovery_id"]
        for row in snapshot["runs"]
        if row["status"] in {"interrupted", "rolled_back"}
    }
    for row in snapshot["journal"]:
        if row["recovery_id"] not in interrupted or int(row["restored"]) == 1:
            continue
        before = json.loads(row["before_json"]) if row["before_json"] else None
        target = zones if row["table_name"] == "zones" else queue
        if before is None:
            target.pop(row["record_id"], None)
        else:
            target[row["record_id"]] = before
    return {
        "zones": [zones[key] for key in sorted(zones)],
        "keys": snapshot["keys"],
        "queue": [queue[key] for key in sorted(queue)],
        "journal": snapshot["journal"],
        "system": snapshot["system"],
    }


def source_hashes() -> tuple[dict[str, str], bool]:
    expected = read_object(MANIFEST).get("files", {})
    if not isinstance(expected, dict):
        return {}, False
    actual: dict[str, str] = {}
    valid = True
    for relative, wanted in expected.items():
        path = ROOT / str(relative)
        try:
            actual[str(relative)] = sha256(path.read_bytes())
        except OSError:
            valid = False
            continue
        valid &= actual[str(relative)] == wanted
    return actual, valid


def context(connection: sqlite3.Connection) -> dict[str, Any]:
    policy = read_object(POLICY)
    inventory = read_object(INVENTORY)
    checkpoint = read_object(CHECKPOINT)
    parent = read_rows(PARENT)
    dns = read_rows(DNS)
    snapshot = database_state(connection)
    base = recovered_state(snapshot)
    hashes, sources_valid = source_hashes()
    source_checkpoint = sha256(
        canonical(
            {
                "source_hashes": hashes,
                "source_revision": int(base["system"]["source_revision"]),
                "zones": base["zones"],
                "keys": base["keys"],
                "checkpoint": checkpoint,
                "inventory": inventory,
                "parent": parent,
                "dns": dns,
            }
        )
    )
    return {
        "policy": policy,
        "inventory": inventory,
        "checkpoint": checkpoint,
        "parent": parent,
        "dns": dns,
        "snapshot": snapshot,
        "base": base,
        "source_hashes": hashes,
        "sources_valid": sources_valid,
        "source_checkpoint": source_checkpoint,
    }


def normalize_locator(value: str) -> str:
    return value[:-4] if value.endswith("#SOA") else value


def normalized(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    rows = []
    for value in plan.get("zone_decisions", []) if isinstance(plan.get("zone_decisions"), list) else []:
        if isinstance(value, dict):
            row = dict(value)
            refs = row.get("evidence_refs")
            if isinstance(refs, list) and all(isinstance(item, str) for item in refs):
                row["evidence_refs"] = sorted({normalize_locator(item) for item in refs})
            rows.append(row)
    result["zone_decisions"] = sorted(rows, key=lambda row: str(row.get("zone_name")))
    journals = plan.get("journal_actions", [])
    result["journal_actions"] = sorted(
        [dict(row) for row in journals if isinstance(row, dict)] if isinstance(journals, list) else [],
        key=lambda row: str(row.get("journal_id")),
    )
    return result


def source_rows(ctx: dict[str, Any], zone_name: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    inv = next(row for row in ctx["inventory"]["zones"] if row["zone_name"] == zone_name)
    zone = next(row for row in ctx["base"]["zones"] if row["zone_name"] == zone_name)
    parent = [row for row in ctx["parent"] if row["zone_name"] == zone_name]
    dns = next(row for row in ctx["dns"] if row["zone_name"] == zone_name)
    checkpoint = next(row for row in ctx["checkpoint"]["zones"] if row["zone_name"] == zone_name)
    return inv, zone, parent, dns, checkpoint


def evidence_for(ctx: dict[str, Any], zone_name: str) -> set[str]:
    inv, _zone, parents, dns, _checkpoint = source_rows(ctx, zone_name)
    refs = {
        f"evidence/key_inventory.json#zones/{zone_name}",
        f"evidence/dns_observations.jsonl#{dns['observation_id']}",
        f"state/stale_checkpoint.json#zones/{zone_name}",
        f"state/dnssec.db#zones/{zone_name}",
        f"zones/{zone_name}.zone",
    }
    for key in (inv.get("old_key_id"), inv.get("new_key_id")):
        if key:
            refs.add(f"keys/{key}.key")
    for row in parents:
        refs.add(f"evidence/parent_ds_observations.jsonl#{row['observation_id']}")
    for row in ctx["base"]["journal"]:
        if row["record_id"] == zone_name:
            refs.add(f"state/dnssec.db#rollover_journal/{row['journal_id']}")
    return refs


def zone_diagnostics(submitted: dict[str, Any], ctx: dict[str, Any], zone_name: str) -> list[str]:
    policy = ctx["policy"]
    inv, zone, parents, dns, _checkpoint = source_rows(ctx, zone_name)
    failed: list[str] = []
    required = set(policy["zone_decision_fields"])
    if set(submitted) != required:
        failed.append("schema: zone decision fields differ from policy")
    now = parse_time(policy["observation_time"])
    role = inv["key_role"]
    new_key = inv.get("new_key_id")
    age = (
        int((now - parse_time(dns["new_dnskey_first_seen"])).total_seconds())
        if dns.get("new_dnskey_first_seen")
        else 0
    )
    expiry = (
        int((parse_time(dns["minimum_rrsig_expiry"]) - now).total_seconds())
        if dns.get("minimum_rrsig_expiry")
        else 0
    )
    if role == "NONE":
        phase = "not_in_rollover"
        dwell = "not_applicable"
        signature = "not_applicable"
        parent_state = "not_applicable"
        action = "preserve_unrelated"
    elif role == "KSK":
        required_probes = set(policy["required_parent_probes"])
        rows = {row["probe"]: row for row in parents}
        all_new = required_probes <= set(rows) and all(new_key in rows[p]["ds_key_ids"] for p in required_probes)
        all_old_only = required_probes <= set(rows) and all(new_key not in rows[p]["ds_key_ids"] for p in required_probes)
        parent_state = "old_and_new_quorum" if all_new else "old_only" if all_old_only else "inconsistent"
        first_new = min((parse_time(row["observed_at"]) for row in parents if new_key in row["ds_key_ids"]), default=now)
        parent_age = int((now - first_new).total_seconds()) if all_new else 0
        dwell = "satisfied" if all_new and parent_age >= int(policy["minimum_parent_ds_dwell_seconds"]) else "insufficient"
        signature = "valid_new_coverage" if new_key in dns["rrsig_key_ids"] and expiry >= int(policy["minimum_signature_validity_seconds"]) else "invalid_or_expiring"
        if parent_state == "old_and_new_quorum" and dwell == "satisfied" and signature == "valid_new_coverage":
            phase, action = "ksk_parent_propagated", "stage_old_ksk_retirement"
        else:
            phase, action = "ksk_double_sign", "monitor_parent_ds"
    else:
        dwell = "satisfied" if age >= int(policy["minimum_dnskey_dwell_seconds"]) else "insufficient"
        parent_state = "not_applicable"
        if expiry < int(policy["minimum_signature_validity_seconds"]):
            signature = "invalid_or_expiring"
        elif new_key in dns["rrsig_key_ids"]:
            signature = "valid_new_coverage"
        else:
            signature = "valid_old_only"
        if signature == "invalid_or_expiring":
            phase, action = "zsk_prepublish", "hold_signature_risk"
        elif dwell == "insufficient":
            phase, action = "zsk_prepublish", "hold_for_dnskey_dwell"
        elif signature == "valid_new_coverage":
            phase, action = "zsk_active", "stage_new_zsk_activation"
        else:
            phase, action = "zsk_prepublish", "preserve_active"
    expected_fields = {
        "key_role": role,
        "rollover_phase": phase,
        "current_serial": int(zone["serial"]),
        "ttl_dwell_state": dwell,
        "signature_state": signature,
        "parent_ds_state": parent_state,
        "action": action,
    }
    categories = {
        "key_role": "key inventory role",
        "rollover_phase": "role-specific phase",
        "current_serial": "recovered zone serial",
        "ttl_dwell_state": "published timing threshold",
        "signature_state": "RRSIG coverage and validity",
        "parent_ds_state": "parent probe set",
        "action": "role-specific guarded action",
    }
    if submitted.get("zone_name") != zone_name:
        failed.append("zone_name: stable zone identity")
    for field, expected in expected_fields.items():
        if submitted.get(field) != expected:
            failed.append(f"{field}: {categories[field]}")
    refs = submitted.get("evidence_refs")
    actual_refs = {normalize_locator(item) for item in refs} if isinstance(refs, list) and all(isinstance(item, str) for item in refs) else set()
    if actual_refs != evidence_for(ctx, zone_name):
        failed.append("evidence_refs: visible zone/key/observation/checkpoint/database evidence set")
    return failed


def plan_diagnostics(plan: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    policy = ctx["policy"]
    top_errors: list[str] = []
    if set(plan) != set(policy["required_top_level_fields"]):
        top_errors.append("top-level fields differ from policy")
    checks = {
        "schema_version": 1,
        "recovery_id": policy["recovery_id"],
        "source_checkpoint": ctx["source_checkpoint"],
        "rollover_id": policy["rollover_id"],
        "external_actions_executed": False,
    }
    for field, wanted in checks.items():
        if plan.get(field) != wanted:
            top_errors.append(f"{field}: invalid published identity or safety value")
    values = plan.get("zone_decisions", [])
    rows = {str(row.get("zone_name")): row for row in values if isinstance(row, dict)} if isinstance(values, list) else {}
    zone_diagnostic: dict[str, list[str]] = {}
    known = [row["zone_name"] for row in ctx["inventory"]["zones"]]
    for zone_name in known:
        if zone_name not in rows:
            zone_diagnostic[zone_name] = ["missing zone decision"]
        else:
            errors = zone_diagnostics(rows[zone_name], ctx, zone_name)
            if errors:
                zone_diagnostic[zone_name] = errors
    for extra in sorted(set(rows) - set(known)):
        zone_diagnostic[extra] = ["zone is outside inventory"]
    if not isinstance(values, list) or len(values) != len(rows):
        top_errors.append("zone decisions contain duplicate or malformed identities")
    journal_values = plan.get("journal_actions", [])
    journal_rows = {str(row.get("journal_id")): row for row in journal_values if isinstance(row, dict)} if isinstance(journal_values, list) else {}
    journal_diagnostic: dict[str, list[str]] = {}
    expected_journals = {
        row["journal_id"]: {
            "journal_id": row["journal_id"],
            "table_name": row["table_name"],
            "record_id": row["record_id"],
            "action": "restore_before_image" if row["before_json"] else "remove_partial_insert",
        }
        for row in ctx["base"]["journal"]
    }
    for journal_id, expected in expected_journals.items():
        row = journal_rows.get(journal_id)
        if row is None:
            journal_diagnostic[journal_id] = ["missing interrupted journal action"]
        elif row != expected:
            journal_diagnostic[journal_id] = ["schema/table/record/action differs from visible journal before-image"]
    for extra in sorted(set(journal_rows) - set(expected_journals)):
        journal_diagnostic[extra] = ["journal is not an unrestored interrupted record"]
    if not isinstance(journal_values, list) or len(journal_values) != len(journal_rows):
        top_errors.append("journal actions contain duplicate or malformed identities")
    return {
        "valid": not top_errors and not zone_diagnostic and not journal_diagnostic,
        "top_errors": top_errors,
        "zone_diagnostics": zone_diagnostic,
        "journal_diagnostics": journal_diagnostic,
    }


def load_plan(path: str) -> dict[str, Any]:
    return normalized(read_object(ROOT / path))


def state_projection(connection: sqlite3.Connection) -> dict[str, Any]:
    value = database_state(connection)
    return {"zones": value["zones"], "keys": value["keys"], "queue": value["queue"], "receipts": value["receipts"]}


def restore_journal(connection: sqlite3.Connection, ctx: dict[str, Any]) -> None:
    for row in ctx["snapshot"]["journal"]:
        if int(row["restored"]) == 1:
            continue
        before = json.loads(row["before_json"]) if row["before_json"] else None
        if row["table_name"] == "zones":
            connection.execute(
                "UPDATE zones SET serial=?,rollover_phase=?,last_change_at=? WHERE zone_name=?",
                (before["serial"], before["rollover_phase"], before["last_change_at"], before["zone_name"]),
            )
        elif row["table_name"] == "staging_queue":
            if before is None:
                connection.execute("DELETE FROM staging_queue WHERE queue_id=?", (row["record_id"],))
            else:
                connection.execute(
                    "INSERT OR REPLACE INTO staging_queue VALUES (?,?,?,?,?,?,?)",
                    tuple(before[key] for key in ("queue_id", "zone_name", "key_role", "action", "status", "requested_by_recovery", "executed")),
                )
        connection.execute("UPDATE rollover_journal SET restored=1 WHERE journal_id=?", (row["journal_id"],))
    connection.execute(
        "UPDATE recovery_runs SET status='rolled_back' WHERE status='interrupted'"
    )


def inspect_command() -> int:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        ctx = context(connection)
    print(json.dumps({
        "rollover_id": ctx["policy"]["rollover_id"],
        "recovery_id": ctx["policy"]["recovery_id"],
        "source_revision": int(ctx["base"]["system"]["source_revision"]),
        "source_checkpoint": ctx["source_checkpoint"],
        "source_bundle_valid": ctx["sources_valid"],
        "zones": [row["zone_name"] for row in ctx["inventory"]["zones"]],
        "interrupted_journals": [{"journal_id": row["journal_id"], "table_name": row["table_name"], "record_id": row["record_id"], "has_before_image": row["before_json"] is not None} for row in ctx["base"]["journal"] if int(row["restored"]) == 0],
        "commands": ["query", "preview", "apply", "stage", "verify", "replay"],
    }, indent=2, sort_keys=True))
    return 0


def query_command(sql: str) -> int:
    statement = sql.strip().rstrip(";")
    lowered = f" {statement.casefold()} "
    allowed = {"zones", "key_state", "staging_queue", "decision_receipts", "recovery_runs", "rollover_journal", "system_state"}
    if not statement.casefold().startswith("select ") or any(token in lowered for token in (" insert ", " update ", " delete ", " pragma ", " attach ")):
        raise ValueError("query accepts one read-only SELECT")
    if not any(re.search(rf"\b{re.escape(name)}\b", lowered) for name in allowed):
        raise ValueError("query must target a published table")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        cursor = connection.execute(statement)
        names = [item[0] for item in cursor.description or []]
        print(json.dumps([dict(zip(names, row, strict=True)) for row in cursor.fetchall()], indent=2, sort_keys=True))
    return 0


def preview_command(path: str) -> int:
    try:
        plan = load_plan(path)
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
            ctx = context(connection)
        report = plan_diagnostics(plan, ctx)
        report.update({"source_bundle_valid": ctx["sources_valid"], "source_checkpoint": ctx["source_checkpoint"], "semantic_plan_digest": sha256(canonical(plan))})
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as error:
        report = {"valid": False, "top_errors": [str(error)], "zone_diagnostics": {}, "journal_diagnostics": {}}
    (ROOT / ".dnssec_preview.json").write_bytes(canonical(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("valid") else 2


def desired_queue(plan: dict[str, Any]) -> list[dict[str, Any]]:
    actionable = {"monitor_parent_ds", "stage_old_ksk_retirement", "hold_for_dnskey_dwell", "stage_new_zsk_activation", "hold_signature_risk"}
    return [
        {
            "queue_id": f"Q-{plan['recovery_id']}-{row['zone_name']}",
            "zone_name": row["zone_name"],
            "key_role": row["key_role"],
            "action": row["action"],
            "status": "staged_local",
            "requested_by_recovery": plan["recovery_id"],
            "executed": 0,
        }
        for row in plan["zone_decisions"]
        if row["action"] in actionable
    ]


def apply_command(path: str) -> int:
    plan = load_plan(path)
    semantic = sha256(canonical(plan))
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        ctx = context(connection)
        prior = connection.execute("SELECT semantic_plan_digest,status FROM recovery_runs WHERE recovery_id=?", (plan.get("recovery_id"),)).fetchone()
    if prior and prior[1] == "committed":
        if prior[0] == semantic:
            print('{"status":"idempotent_noop","mutation_count":0}')
            return 0
        print('{"status":"rejected","reason":"recovery identity conflict"}')
        return 4
    report = plan_diagnostics(plan, ctx)
    if not ctx["sources_valid"] or not report["valid"]:
        print(json.dumps({"status": "rejected", "reason": "source or plan validation failed", **report}, indent=2, sort_keys=True))
        return 2
    with sqlite3.connect(DB) as connection:
        connection.execute("BEGIN IMMEDIATE")
        revision = connection.execute("SELECT value FROM system_state WHERE key='source_revision'").fetchone()
        if not revision or int(revision[0]) != int(ctx["base"]["system"]["source_revision"]):
            connection.rollback()
            print('{"status":"rejected","reason":"stale source revision"}')
            return 3
        restore_journal(connection, ctx)
        connection.execute("DELETE FROM staging_queue WHERE requested_by_recovery=?", (plan["recovery_id"],))
        connection.executemany(
            "INSERT INTO staging_queue VALUES (?,?,?,?,?,?,?)",
            [tuple(row[key] for key in ("queue_id", "zone_name", "key_role", "action", "status", "requested_by_recovery", "executed")) for row in desired_queue(plan)],
        )
        connection.executemany(
            "INSERT INTO decision_receipts VALUES (?,?,?,?,?,?,?,?,?)",
            [(plan["recovery_id"], row["zone_name"], row["key_role"], row["rollover_phase"], row["current_serial"], row["ttl_dwell_state"], row["signature_state"], row["parent_ds_state"], row["action"]) for row in plan["zone_decisions"]],
        )
        projection = state_projection(connection)
        state_digest = sha256(canonical(projection))
        connection.execute(
            "INSERT OR REPLACE INTO recovery_runs VALUES (?,?,?,?,?)",
            (plan["recovery_id"], plan["source_checkpoint"], semantic, state_digest, "committed"),
        )
        connection.commit()
    print(json.dumps({"status": "committed", "semantic_plan_digest": semantic, "semantic_state_digest": state_digest, "external_actions_executed": False}, sort_keys=True))
    return 0


def stage_payload(plan: dict[str, Any], state_digest: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    queue = [{"zone_name": row["zone_name"], "key_role": row["key_role"], "action": row["action"], "status": "queued_local", "executed": False} for row in desired_queue(plan)]
    bundle = {"schema_version": 1, "rollover_id": plan["rollover_id"], "recovery_id": plan["recovery_id"], "requests": queue, "zones_signed": False, "zones_published": False, "parent_changes_executed": False, "external_actions_executed": False}
    manifest = {"bundle_sha256": sha256(canonical(bundle)), "semantic_plan_digest": sha256(canonical(plan)), "semantic_state_digest": state_digest, "source_checkpoint": plan["source_checkpoint"]}
    receipt = {"manifest_sha256": sha256(canonical(manifest)), "queue_count": len(queue), "status": "local_staged", "external_action": False}
    return bundle, manifest, receipt


def stage_command(path: str) -> int:
    plan = load_plan(path)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        run = connection.execute("SELECT semantic_plan_digest,semantic_state_digest,status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    if not run or run[2] != "committed" or run[0] != sha256(canonical(plan)):
        print('{"status":"rejected","reason":"plan is not committed"}')
        return 2
    bundle, manifest, receipt = stage_payload(plan, run[1])
    (ROOT / "staging").mkdir(exist_ok=True)
    (ROOT / "staging/dnssec_change_queue.json").write_bytes(canonical(bundle))
    (ROOT / "staging/queue_manifest.json").write_bytes(canonical(manifest))
    (ROOT / "state/recovery_receipt.json").write_bytes(canonical(receipt))
    print(json.dumps({"status": "local_staged", "queue_count": len(bundle["requests"])}))
    return 0


def verify_state(plan: dict[str, Any]) -> tuple[bool, list[str], str]:
    errors: list[str] = []
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        projection = state_projection(connection)
        run = connection.execute("SELECT source_checkpoint,semantic_plan_digest,semantic_state_digest,status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    state_digest = sha256(canonical(projection))
    if not run or tuple(run) != (plan["source_checkpoint"], sha256(canonical(plan)), state_digest, "committed"):
        errors.append("recovery run identity or state digest does not close")
    queue = sorted(desired_queue(plan), key=lambda row: row["queue_id"])
    actual = [row for row in projection["queue"] if row["requested_by_recovery"] == plan["recovery_id"]]
    if actual != queue:
        errors.append("database queue differs from the validated local plan")
    try:
        bundle = read_object(ROOT / "staging/dnssec_change_queue.json")
        manifest = read_object(ROOT / "staging/queue_manifest.json")
        receipt = read_object(ROOT / "state/recovery_receipt.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return False, errors + [str(error)], state_digest
    expected = stage_payload(plan, state_digest)
    if (bundle, manifest, receipt) != expected:
        errors.append("staging bundle manifest or receipt hash closure failed")
    return not errors, errors, state_digest


def verify_command(path: str) -> int:
    plan = load_plan(path)
    ok, errors, state_digest = verify_state(plan)
    report = {"status": "pass" if ok else "fail", "errors": errors, "semantic_plan_digest": sha256(canonical(plan)), "semantic_state_digest": state_digest, "external_actions_executed": False}
    (ROOT / "state/verification.json").write_bytes(canonical(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 2


def replay_command(path: str) -> int:
    plan = load_plan(path)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        ctx = context(connection)
        run = connection.execute("SELECT semantic_plan_digest,status FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    report = plan_diagnostics(plan, ctx)
    ok, errors, _ = verify_state(plan)
    semantic = sha256(canonical(plan))
    if not ctx["sources_valid"] or not report["valid"] or not run or tuple(run) != (semantic, "committed") or not ok:
        print(json.dumps({"status": "rejected", "reason": "stale, conflicting, or unverified replay", "errors": errors}, sort_keys=True))
        return 2
    replay = {"status": "idempotent_noop", "mutation_count": 0, "semantic_plan_digest": semantic}
    (ROOT / "state/replay_report.json").write_bytes(canonical(replay))
    print(json.dumps(replay, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline DNSSEC rollover recovery controller")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    query = commands.add_parser("query")
    query.add_argument("sql")
    for name in ("preview", "apply", "stage", "verify", "replay"):
        command = commands.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect_command()
        if args.command == "query":
            return query_command(args.sql)
        return {"preview": preview_command, "apply": apply_command, "stage": stage_command, "verify": verify_command, "replay": replay_command}[args.command](args.plan)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as error:
        print(json.dumps({"status": "error", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
