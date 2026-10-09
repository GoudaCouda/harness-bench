#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/incident.db"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def table_rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def restored_base(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    tables = {
        "acquisition_state": {
            row["request_id"]: row for row in table_rows(connection, "acquisition_state", "request_id")
        },
        "containment_state": {
            row["entity_id"]: row for row in table_rows(connection, "containment_state", "entity_id")
        },
    }
    interrupted = {
        row["recovery_id"]
        for row in table_rows(connection, "recovery_runs", "recovery_id")
        if row["status"] == "interrupted"
    }
    for journal in table_rows(connection, "before_image_journal", "journal_id"):
        if journal["recovery_id"] not in interrupted or not journal["applied"]:
            continue
        before = json.loads(journal["before_json"])
        key = "request_id" if journal["table_name"] == "acquisition_state" else "entity_id"
        tables[journal["table_name"]][before[key]] = before
    return {
        name: [items[key] for key in sorted(items)] for name, items in tables.items()
    }


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


def _catalog(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {row["blob_id"]: row for row in table_rows(connection, "evidence_catalog", "blob_id")}


def _blob_state(root: Path, catalog: dict[str, dict[str, Any]], blob_id: str) -> tuple[str, str]:
    row = catalog[blob_id]
    try:
        actual = sha((root / row["relative_path"]).read_bytes())
    except OSError:
        return "hash_mismatch", "missing"
    if actual != row["expected_sha256"]:
        return "hash_mismatch", actual
    predecessor = row["predecessor_blob_id"]
    if predecessor:
        prior = catalog.get(predecessor)
        if prior is None or prior["expected_sha256"] != row["recorded_predecessor_sha256"]:
            return "chain_break", actual
    return "valid", actual


def _load_authority(root: Path) -> dict[str, Any]:
    policy = load_json(root / "policy/incident_policy.json")
    valid_sources, _, source_hashes = source_status(root)
    with sqlite3.connect(f"file:{root / 'state/incident.db'}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        catalog = _catalog(connection)
        requests = table_rows(connection, "acquisition_requests", "request_id")
        entities = table_rows(connection, "entities", "entity_id")
        base = restored_base(connection)
        revision = dict(connection.execute("SELECT key,value FROM system_state"))["source_revision"]
    checkpoint_payload = {
        "source_hashes": source_hashes,
        "source_revision": int(revision),
        "acquisition_requests": requests,
        "containment_state": base["containment_state"],
    }
    checkpoint = sha(canonical(checkpoint_payload)) if valid_sources else "invalid-source-bundle"
    events = [
        json.loads(line)
        for line in (root / "evidence/events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "policy": policy,
        "checkpoint": checkpoint,
        "catalog": catalog,
        "requests": requests,
        "entities": entities,
        "base_containment": {
            row["entity_id"]: row for row in base["containment_state"]
        },
        "events": events,
    }


def _event_rule(
    root: Path,
    catalog: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    events: list[dict[str, Any]],
    event: dict[str, Any],
) -> str:
    first = next(row for row in events if row["event_id"] == event["event_id"])
    if first["delivery_id"] != event["delivery_id"]:
        return "duplicate_delivery_ignored"
    if event["incident_id"] != policy["incident_id"]:
        return "identity_mismatch_ignored"
    if _blob_state(root, catalog, event["blob_id"])[0] == "hash_mismatch":
        return "hash_mismatch_quarantined"
    eligible = []
    seen: set[str] = set()
    for candidate in events:
        if candidate["event_id"] in seen:
            continue
        seen.add(candidate["event_id"])
        if candidate["incident_id"] != policy["incident_id"]:
            continue
        if _blob_state(root, catalog, candidate["blob_id"])[0] == "hash_mismatch":
            continue
        if candidate["stream"] == event["stream"]:
            eligible.append(int(candidate["sequence"]))
    return (
        "applied_current"
        if int(event["sequence"]) == max(eligible)
        else "superseded_by_newer_sequence"
    )


def _acquisition_rule(
    root: Path,
    catalog: dict[str, dict[str, Any]],
    requests: list[dict[str, Any]],
    policy: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    phases = {
        name: index for index, name in enumerate(policy["acquisition_phase_order"])
    }
    ordered = sorted(requests, key=lambda row: (phases[row["phase"]], row["request_id"]))
    state, _ = _blob_state(root, catalog, request["blob_id"])
    action = {
        "valid": "preserve_offline",
        "hash_mismatch": "quarantine_hash_mismatch",
        "chain_break": "quarantine_chain_break",
    }[state]
    return {
        "request_id": request["request_id"],
        "target_type": request["target_type"],
        "target_id": request["target_id"],
        "blob_id": request["blob_id"],
        "phase": request["phase"],
        "depends_on": request["depends_on"],
        "order": next(
            index for index, row in enumerate(ordered, 1)
            if row["request_id"] == request["request_id"]
        ),
        "action": action,
        "custody_state": state,
    }


def _scope_rule(entity: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    classification = entity["observed_classification"]
    if (
        entity["entity_type"] == "host"
        and classification == "confirmed"
        and observed["observed_external"]
    ):
        action, boundary = "preserve_observed_isolation", "observed_external_complete"
    elif entity["entity_type"] == "session" and classification == "compromised":
        action, boundary = "stage_session_disable", "pending_external_irreversible"
    elif entity["entity_type"] == "account" and classification == "session_scoped_signal":
        action, boundary = "preserve_account_scope", "no_account_expansion"
    elif entity["entity_type"] == "host" and classification == "ambiguous":
        action, boundary = "analyst_review_no_containment", "ambiguity_preserved"
    else:
        action, boundary = "observe_no_containment", "clean_no_action"
    return {
        "entity_type": entity["entity_type"],
        "entity_id": entity["entity_id"],
        "action": action,
        "boundary": boundary,
    }


def _semantic(plan: dict[str, Any]) -> list[Any]:
    acquisitions = []
    for row in plan.get("acquisitions", []):
        if isinstance(row, dict):
            acquisitions.append({key: row.get(key) for key in row if key != "evidence_refs"})
    return [
        "incident-recovery-semantic-v1",
        plan.get("schema_version"),
        plan.get("incident_id"),
        plan.get("recovery_id"),
        plan.get("source_checkpoint"),
        sorted(plan.get("event_dispositions", []), key=lambda row: str(row.get("delivery_id"))),
        sorted(acquisitions, key=lambda row: str(row.get("request_id"))),
        sorted(plan.get("scope_actions", []), key=lambda row: str(row.get("entity_id"))),
        plan.get("external_actions_executed"),
    ]


def _refs_valid(root: Path, actual: dict[str, Any], blob_id: str) -> bool:
    refs = actual.get("evidence_refs")
    if not isinstance(refs, list):
        return False
    with sqlite3.connect(f"file:{root / 'state/incident.db'}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        catalog = _catalog(connection)
    item = catalog[blob_id]
    _, actual_hash = _blob_state(root, catalog, blob_id)
    normalized = {str(ref).strip().casefold().replace("./", "", 1) for ref in refs}
    return item["relative_path"].casefold() in normalized or f"sha256:{actual_hash}" in normalized


def validate_plan(root: Path, plan: Any) -> dict[str, Any]:
    authority = _load_authority(root)
    errors: dict[str, list[dict[str, Any]]] = {
        name: []
        for name in ("plan", "event_dispositions", "acquisitions", "scope_actions")
    }
    if not isinstance(plan, dict):
        errors["plan"].append({"field": "$", "error": "plan must be a JSON object"})
        return {"valid": False, "errors": errors, "semantic_digest": None}
    required = {
        "schema_version", "incident_id", "recovery_id", "source_checkpoint",
        "event_dispositions", "acquisitions", "scope_actions",
        "external_actions_executed",
    }
    if set(plan) != required:
        errors["plan"].append({"field": "$", "error": "top-level fields differ", "required": sorted(required)})
    scalar_rules = {
        "schema_version": 1,
        "incident_id": authority["policy"]["incident_id"],
        "recovery_id": authority["policy"]["recovery_id"],
        "source_checkpoint": authority["checkpoint"],
        "external_actions_executed": False,
    }
    for field, value in scalar_rules.items():
        if plan.get(field) != value:
            errors["plan"].append({"field": field, "error": "value does not match current local authority"})

    source_groups = {
        "event_dispositions": (
            "delivery_id",
            {row["delivery_id"]: row for row in authority["events"]},
        ),
        "acquisitions": (
            "request_id",
            {row["request_id"]: row for row in authority["requests"]},
        ),
        "scope_actions": (
            "entity_id",
            {row["entity_id"]: row for row in authority["entities"]},
        ),
    }
    for group, (key, sources) in source_groups.items():
        actual_rows = plan.get(group)
        if not isinstance(actual_rows, list):
            errors[group].append({"id": "*", "field": group, "error": "must be an array"})
            continue
        actual_map = {str(row.get(key)): row for row in actual_rows if isinstance(row, dict) and row.get(key)}
        if len(actual_map) != len(actual_rows):
            errors[group].append({"id": "*", "field": key, "error": "duplicate or malformed object key"})
        for identifier in sorted(set(actual_map) | set(sources)):
            if identifier not in sources:
                errors[group].append({"id": identifier, "field": key, "error": "unknown object"})
                continue
            if identifier not in actual_map:
                errors[group].append({"id": identifier, "field": key, "error": "missing object"})
                continue
            left = dict(actual_map[identifier])
            source = sources[identifier]
            if group == "event_dispositions":
                right = {
                    field: source[field]
                    for field in ("delivery_id", "event_id", "stream", "sequence")
                } | {
                    "disposition": _event_rule(
                        root, authority["catalog"], authority["policy"],
                        authority["events"], source,
                    )
                }
            elif group == "acquisitions":
                right = _acquisition_rule(
                    root, authority["catalog"], authority["requests"],
                    authority["policy"], source,
                )
            else:
                right = _scope_rule(
                    source, authority["base_containment"][identifier]
                )
            if group == "acquisitions":
                left.pop("evidence_refs", None)
            for field, value in right.items():
                if left.get(field) != value:
                    errors[group].append({"id": identifier, "field": field, "error": "value violates source-derived rule"})
            if set(left) != set(right):
                errors[group].append({"id": identifier, "field": "$", "error": "object fields differ", "required": sorted(right)})
            if group == "acquisitions" and not _refs_valid(
                root, actual_map[identifier], source["blob_id"]
            ):
                errors[group].append({"id": identifier, "field": "evidence_refs", "error": "cite this blob by local path or actual sha256"})
    valid = not any(errors.values())
    return {
        "valid": valid,
        "errors": errors,
        "semantic_digest": sha(canonical(_semantic(plan))) if valid else None,
    }


def read_plan(path: str) -> Any:
    try:
        return load_json(ROOT / path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read plan: {exc}") from exc


def preview(path: str) -> None:
    try:
        plan = read_plan(path)
        result = validate_plan(ROOT, plan)
    except ValueError as exc:
        result = {"valid": False, "errors": {"plan": [{"id": "*", "field": "$", "error": str(exc)}]}, "semantic_digest": None}
    write_json(ROOT / ".incident_preview.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(2)


def restore_before_images(connection: sqlite3.Connection) -> None:
    interrupted = {
        row[0] for row in connection.execute("SELECT recovery_id FROM recovery_runs WHERE status='interrupted'")
    }
    for recovery_id, table, before_json, applied in connection.execute(
        "SELECT recovery_id,table_name,before_json,applied FROM before_image_journal ORDER BY journal_id"
    ):
        if recovery_id not in interrupted or not applied:
            continue
        before = json.loads(before_json)
        if table == "acquisition_state":
            connection.execute(
                "UPDATE acquisition_state SET status=?,preserved_sha256=?,version=? WHERE request_id=?",
                (before["status"], before["preserved_sha256"], before["version"], before["request_id"]),
            )
        elif table == "containment_state":
            connection.execute(
                "UPDATE containment_state SET entity_type=?,status=?,observed_external=?,version=? WHERE entity_id=?",
                (before["entity_type"], before["status"], before["observed_external"], before["version"], before["entity_id"]),
            )


def apply(path: str, *, replay_only: bool = False) -> None:
    plan = read_plan(path)
    result = validate_plan(ROOT, plan)
    if not result["valid"]:
        write_json(ROOT / ".incident_preview.json", result)
        raise SystemExit("plan invalid; inspect .incident_preview.json")
    recovery_id = plan["recovery_id"]
    digest = result["semantic_digest"]
    with sqlite3.connect(DB) as connection:
        existing = connection.execute(
            "SELECT status,source_checkpoint,semantic_digest FROM recovery_runs WHERE recovery_id=?", (recovery_id,)
        ).fetchone()
        if existing:
            if existing[1] == plan["source_checkpoint"] and existing[2] == digest and existing[0] == "applied_local":
                if replay_only:
                    write_json(ROOT / "state/replay_report.json", {"recovery_id": recovery_id, "status": "semantic_noop", "semantic_digest": digest})
                    print("semantic replay: no database mutation")
                    return
                print("already applied: semantic no-op")
                return
            raise SystemExit("recovery identity conflict; database unchanged")
        if replay_only:
            raise SystemExit("no applied recovery exists; use apply first")
        connection.execute("BEGIN IMMEDIATE")
        restore_before_images(connection)
        catalog = _catalog(connection)
        for row in plan["acquisitions"]:
            status = {
                "preserve_offline": "preserved_offline",
                "quarantine_hash_mismatch": "quarantined_hash_mismatch",
                "quarantine_chain_break": "quarantined_chain_break",
            }[row["action"]]
            _, actual_digest = _blob_state(ROOT, catalog, row["blob_id"])
            connection.execute(
                "UPDATE acquisition_state SET status=?,preserved_sha256=?,version=version+1 WHERE request_id=?",
                (
                    status,
                    actual_digest if status == "preserved_offline" else None,
                    row["request_id"],
                ),
            )
        for row in plan["event_dispositions"]:
            connection.execute("INSERT INTO event_receipts VALUES(?,?,?,?)", (row["delivery_id"], row["event_id"], row["disposition"], recovery_id))
        for row in plan["scope_actions"]:
            connection.execute("INSERT INTO scope_queue VALUES(?,?,?,?,?,0)", (row["entity_id"], row["entity_type"], row["action"], row["boundary"], "staged_offline"))
        connection.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,0)", (recovery_id, "applied_local", plan["source_checkpoint"], digest))
        connection.commit()
    write_json(ROOT / "state/recovery_receipt.json", {"recovery_id": recovery_id, "source_checkpoint": plan["source_checkpoint"], "semantic_digest": digest, "status": "applied_local", "external_actions_executed": False})
    print("local recovery projection applied")


def stage(path: str) -> None:
    plan = read_plan(path)
    result = validate_plan(ROOT, plan)
    if not result["valid"]:
        raise SystemExit("plan invalid")
    with sqlite3.connect(DB) as connection:
        row = connection.execute("SELECT status,semantic_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    if row != ("applied_local", result["semantic_digest"]):
        raise SystemExit("matching local apply required before stage")
    selected = []
    for acquisition in plan["acquisitions"]:
        if acquisition["action"] != "preserve_offline":
            continue
        selected.append({key: acquisition[key] for key in ("request_id", "target_type", "target_id", "blob_id", "phase", "order")})
    bundle = {"incident_id": plan["incident_id"], "recovery_id": plan["recovery_id"], "objects": selected, "external_delivery": False}
    write_json(ROOT / "staging/evidence_bundle.json", bundle)
    write_json(ROOT / "staging/bundle_manifest.json", {"bundle_sha256": sha(canonical(bundle)), "object_count": len(selected), "semantic_digest": result["semantic_digest"], "external_delivery": False})
    print("offline evidence bundle staged")


def verify(path: str) -> None:
    plan = read_plan(path)
    result = validate_plan(ROOT, plan)
    errors = []
    bundle = load_json(ROOT / "staging/evidence_bundle.json")
    manifest = load_json(ROOT / "staging/bundle_manifest.json")
    if manifest.get("bundle_sha256") != sha(canonical(bundle)):
        errors.append("bundle digest mismatch")
    with sqlite3.connect(DB) as connection:
        receipt_count = connection.execute("SELECT COUNT(*) FROM event_receipts WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()[0]
        queue_count = connection.execute("SELECT COUNT(*) FROM scope_queue").fetchone()[0]
        external_count = connection.execute("SELECT COUNT(*) FROM scope_queue WHERE external_action != 0").fetchone()[0]
    if receipt_count != len(plan["event_dispositions"]):
        errors.append("event receipt closure mismatch")
    if queue_count != len(plan["scope_actions"]):
        errors.append("scope queue closure mismatch")
    if external_count:
        errors.append("external action boundary violated")
    verification = {"verified": result["valid"] and not errors, "errors": errors, "source_checkpoint": plan["source_checkpoint"], "semantic_digest": result["semantic_digest"], "bundle_sha256": manifest.get("bundle_sha256"), "external_actions_executed": False}
    write_json(ROOT / "state/verification.json", verification)
    print(json.dumps(verification, indent=2, sort_keys=True))
    if not verification["verified"]:
        raise SystemExit(2)


def inspect() -> None:
    valid, expected, actual = source_status(ROOT)
    with sqlite3.connect(DB) as connection:
        summary = {
            "source_manifest_valid": valid,
            "source_mismatches": sorted(name for name in expected if expected[name] != actual[name]),
            "tables": {name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("entities", "evidence_catalog", "acquisition_requests", "acquisition_state", "containment_state", "recovery_runs", "before_image_journal")},
            "interrupted_journal": table_rows(connection, "before_image_journal", "journal_id"),
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


def query(sql: str) -> None:
    if not sql.lstrip().casefold().startswith("select") or ";" in sql.rstrip().rstrip(";"):
        raise SystemExit("query accepts one SELECT statement")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        print(json.dumps([dict(row) for row in connection.execute(sql)], indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline incident evidence recovery controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    query_parser = sub.add_parser("query")
    query_parser.add_argument("sql")
    for name in ("preview", "apply", "stage", "verify", "replay"):
        command = sub.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    if args.command == "inspect":
        inspect()
    elif args.command == "query":
        query(args.sql)
    elif args.command == "preview":
        preview(args.plan)
    elif args.command == "apply":
        apply(args.plan)
    elif args.command == "stage":
        stage(args.plan)
    elif args.command == "verify":
        verify(args.plan)
    elif args.command == "replay":
        apply(args.plan, replay_only=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, sqlite3.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
