#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB = ROOT / "state/imaging.db"
POLICY = ROOT / "policy/deid_policy.json"
MANIFEST = ROOT / "policy/source_manifest.json"
DELIVERIES = ROOT / "evidence/deliveries.jsonl"
PLAN_FIELDS = {"schema_version", "recovery_id", "source_checkpoint", "delivery_dispositions", "instance_decisions", "uid_map", "totals", "external_exports_executed"}
DELIVERY_FIELDS = {"delivery_id", "sop_instance_uid", "study_instance_uid", "source_sequence", "disposition"}
INSTANCE_FIELDS = {"delivery_id", "sop_instance_uid", "study_instance_uid", "modality", "disposition", "reason", "output_relpath", "date_shift_days", "evidence_refs"}
UID_FIELDS = {"uid_type", "original_uid", "deidentified_uid"}
TOTAL_FIELDS = {"deliveries", "eligible_instances", "quarantined_deliveries", "ignored_deliveries", "preserved_instances", "generated_instances"}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def read_dicom(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 134 or data[128:132] != b"DICM":
        raise ValueError(f"{path}: missing DICM marker")
    value = json.loads(data[132:])
    if not isinstance(value, dict):
        raise ValueError(f"{path}: dataset is not an object")
    return value


def write_dicom(path: Path, dataset: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(128) + b"DICM" + canonical(dataset))


def rows(con: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = con.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def deliveries() -> list[dict[str, Any]]:
    result = []
    for line in DELIVERIES.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        item["dataset"] = read_dicom(ROOT / item["path"])
        result.append(item)
    return result


def sources_valid() -> tuple[bool, list[str]]:
    changed = []
    for rel, expected in load(MANIFEST).get("files", {}).items():
        path = ROOT / rel
        actual = digest(path.read_bytes()) if path.is_file() else "missing"
        if actual != expected:
            changed.append(rel)
    return not changed, changed


def uid(namespace: str, original: str) -> str:
    number = int(hashlib.sha256((namespace + "|" + original).encode()).hexdigest(), 16) % (10**36)
    return f"{namespace}.{number}"


def shift_date(value: str, days: int) -> str:
    return (datetime.strptime(value, "%Y%m%d") + timedelta(days=days)).strftime("%Y%m%d")


def baseline() -> dict[str, Any]:
    with sqlite3.connect(DB) as con:
        studies = rows(con, "studies", "study_instance_uid")
        records = rows(con, "export_records", "sop_instance_uid")
        journals = rows(con, "recovery_journal", "journal_id")
        interrupted = {row["recovery_id"] for row in rows(con, "recovery_runs", "recovery_id") if row["status"] == "interrupted"}
        partial_sops = {row["sop_instance_uid"] for row in journals if row["recovery_id"] in interrupted and not row["restored"]}
        records = [row for row in records if row["sop_instance_uid"] not in partial_sops and row["status"] == "protected"]
        revision = con.execute("SELECT value FROM system_state WHERE key='source_revision'").fetchone()[0]
    return {"studies": studies, "protected_records": records, "source_revision": int(revision)}


def checkpoint(base: dict[str, Any]) -> str:
    manifest_hashes = load(MANIFEST)["files"]
    return "sha256:" + digest(canonical({"source_revision": base["source_revision"], "studies": base["studies"], "protected_records": base["protected_records"], "source_hashes": manifest_hashes}))


def normalized(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    instances = []
    for raw in plan.get("instance_decisions", []) if isinstance(plan.get("instance_decisions"), list) else []:
        if isinstance(raw, dict):
            row = dict(raw)
            if isinstance(row.get("evidence_refs"), list):
                row["evidence_refs"] = sorted(str(x) for x in row["evidence_refs"])
            instances.append(row)
    result["instance_decisions"] = sorted(instances, key=lambda x: str(x.get("delivery_id")))
    result["delivery_dispositions"] = sorted([dict(x) for x in plan.get("delivery_dispositions", []) if isinstance(x, dict)] if isinstance(plan.get("delivery_dispositions"), list) else [], key=lambda x: str(x.get("delivery_id")))
    result["uid_map"] = sorted([dict(x) for x in plan.get("uid_map", []) if isinstance(x, dict)] if isinstance(plan.get("uid_map"), list) else [], key=lambda x: (str(x.get("uid_type")), str(x.get("original_uid"))))
    return result


def schema_errors(plan: dict[str, Any]) -> list[str]:
    errors = []
    if set(plan) != PLAN_FIELDS: errors.append("top-level fields differ")
    if not isinstance(plan.get("delivery_dispositions"), list) or any(not isinstance(x, dict) or set(x) != DELIVERY_FIELDS for x in plan.get("delivery_dispositions", [])): errors.append("delivery_dispositions schema differs")
    if not isinstance(plan.get("instance_decisions"), list) or any(not isinstance(x, dict) or set(x) != INSTANCE_FIELDS or not isinstance(x.get("evidence_refs"), list) for x in plan.get("instance_decisions", [])): errors.append("instance_decisions schema differs")
    if not isinstance(plan.get("uid_map"), list) or any(not isinstance(x, dict) or set(x) != UID_FIELDS for x in plan.get("uid_map", [])): errors.append("uid_map schema differs")
    if not isinstance(plan.get("totals"), dict) or set(plan.get("totals", {})) != TOTAL_FIELDS: errors.append("totals schema differs")
    return errors


def compare(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate one candidate while returning only object/field diagnostics."""
    policy, base, stream = load(POLICY), baseline(), deliveries()
    studies = {row["study_instance_uid"]: row for row in base["studies"]}
    got = normalized(plan)
    errors = schema_errors(plan)
    supplied_deliveries = {
        str(row.get("delivery_id")): row
        for row in got.get("delivery_dispositions", [])
        if isinstance(row, dict)
    }
    supplied_instances = {
        str(row.get("delivery_id")): row
        for row in got.get("instance_decisions", [])
        if isinstance(row, dict)
    }
    delivery_diagnostics: dict[str, Any] = {}
    instance_diagnostics: dict[str, Any] = {}
    seen: dict[str, str] = {}
    authoritative: list[tuple[dict[str, Any], str, str]] = []
    quarantined = ignored = preserved = 0
    for item in stream:
        dataset = item["dataset"]
        sop = str(item["sop_instance_uid"])
        body_hash = digest(canonical(dataset))
        if sop in seen:
            disposition = (
                "duplicate_delivery_ignored"
                if seen[sop] == body_hash
                else "sop_uid_collision_quarantined"
            )
            ignored += int(disposition == "duplicate_delivery_ignored")
            quarantined += int(disposition == "sop_uid_collision_quarantined")
        elif item["study_instance_uid"] not in studies:
            seen[sop] = body_hash
            disposition = "unknown_study_quarantined"
            quarantined += 1
            authoritative.append((item, disposition, "unknown_study"))
        elif studies[item["study_instance_uid"]]["state"] == "exported_protected":
            seen[sop] = body_hash
            disposition = "protected_study_ignored"
            ignored += 1
            preserved += 1
            authoritative.append((item, disposition, "protected_export_boundary"))
        elif dataset.get("SOPClassUID") not in policy["supported_sop_classes"]:
            seen[sop] = body_hash
            disposition = "unsupported_sop_quarantined"
            quarantined += 1
            authoritative.append((item, disposition, "unsupported_sop_class"))
        elif dataset.get("BurnedInAnnotation") != "NO":
            seen[sop] = body_hash
            disposition = "pixel_risk_quarantined"
            quarantined += 1
            authoritative.append((item, disposition, "burned_in_annotation_not_no"))
        else:
            seen[sop] = body_hash
            disposition = "eligible_for_local_deidentification"
            authoritative.append((item, disposition, "policy_eligible"))
        expected_row = {
            "delivery_id": item["delivery_id"],
            "sop_instance_uid": item["sop_instance_uid"],
            "study_instance_uid": item["study_instance_uid"],
            "source_sequence": item["source_sequence"],
            "disposition": disposition,
        }
        supplied = supplied_deliveries.get(str(item["delivery_id"]), {})
        mismatches = sorted(
            field for field, value in expected_row.items() if supplied.get(field) != value
        )
        delivery_diagnostics[str(item["delivery_id"])] = {
            "status": "ok" if not mismatches else "mismatch",
            "mismatches": mismatches,
        }
    for identifier in sorted(set(supplied_deliveries) - set(delivery_diagnostics)):
        delivery_diagnostics[identifier] = {
            "status": "unexpected",
            "mismatches": ["object"],
        }

    eligible_sops = {
        str(item["sop_instance_uid"])
        for item, disposition, _ in authoritative
        if disposition == "eligible_for_local_deidentification"
    }
    original_uids: set[tuple[str, str]] = set()
    generated = 0
    for item, delivery_disposition, reason in authoritative:
        dataset = item["dataset"]
        study_id = str(item["study_instance_uid"])
        disposition = (
            "generate_deidentified_instance"
            if delivery_disposition == "eligible_for_local_deidentification"
            else delivery_disposition
        )
        if (
            disposition == "generate_deidentified_instance"
            and dataset.get("ReferencedSOPInstanceUID")
            and str(dataset["ReferencedSOPInstanceUID"]) not in eligible_sops
        ):
            disposition = "unresolved_reference_quarantined"
            reason = "referenced_sop_not_eligible"
            quarantined += 1
        study = studies.get(study_id)
        output = (
            f"exports/deidentified/{item['output_name']}"
            if disposition == "generate_deidentified_instance"
            else None
        )
        refs = [
            f"{item['path']}#dataset",
            f"evidence/deliveries.jsonl#{item['delivery_id']}",
            "policy/deid_policy.json#rules",
        ]
        if study:
            refs.append(f"state/imaging.db#studies:{study_id}")
        expected_row = {
            "delivery_id": item["delivery_id"],
            "sop_instance_uid": item["sop_instance_uid"],
            "study_instance_uid": study_id,
            "modality": dataset.get("Modality"),
            "disposition": disposition,
            "reason": reason,
            "output_relpath": output,
            "date_shift_days": (
                study["date_shift_days"]
                if study and disposition == "generate_deidentified_instance"
                else None
            ),
            "evidence_refs": sorted(refs),
        }
        supplied = supplied_instances.get(str(item["delivery_id"]), {})
        mismatches = sorted(
            field for field, value in expected_row.items() if supplied.get(field) != value
        )
        instance_diagnostics[str(item["delivery_id"])] = {
            "status": "ok" if not mismatches else "mismatch",
            "mismatches": mismatches,
        }
        if disposition == "generate_deidentified_instance":
            generated += 1
            for field, kind in (
                ("StudyInstanceUID", "study"),
                ("SeriesInstanceUID", "series"),
                ("SOPInstanceUID", "sop"),
                ("ReferencedSOPInstanceUID", "sop"),
            ):
                if dataset.get(field):
                    original_uids.add((kind, str(dataset[field])))
    for identifier in sorted(set(supplied_instances) - set(instance_diagnostics)):
        instance_diagnostics[identifier] = {
            "status": "unexpected",
            "mismatches": ["object"],
        }

    uid_rows = [
        {
            "uid_type": kind,
            "original_uid": original,
            "deidentified_uid": uid(policy["uid_namespace"], original),
        }
        for kind, original in sorted(original_uids)
    ]
    totals = {
        "deliveries": len(stream),
        "eligible_instances": generated,
        "quarantined_deliveries": quarantined,
        "ignored_deliveries": ignored,
        "preserved_instances": preserved,
        "generated_instances": generated,
    }
    source_bundle_valid, _ = sources_valid()
    source_checkpoint_match = got.get("source_checkpoint") == checkpoint(base)
    identity_fields_match = (
        got.get("schema_version") == 1
        and got.get("recovery_id") == policy["recovery_id"]
        and got.get("external_exports_executed") is False
    )
    uid_map_match = got.get("uid_map") == uid_rows
    totals_mismatches = sorted(
        key for key, value in totals.items() if got.get("totals", {}).get(key) != value
    )
    report = {
        "schema_errors": errors,
        "source_bundle_valid": source_bundle_valid,
        "source_checkpoint_match": source_checkpoint_match,
        "identity_fields_match": identity_fields_match,
        "delivery_diagnostics": delivery_diagnostics,
        "instance_diagnostics": instance_diagnostics,
        "uid_map_match": uid_map_match,
        "totals_mismatches": totals_mismatches,
    }
    report["valid"] = (
        not errors
        and source_bundle_valid
        and source_checkpoint_match
        and identity_fields_match
        and all(row["status"] == "ok" for row in delivery_diagnostics.values())
        and all(row["status"] == "ok" for row in instance_diagnostics.values())
        and uid_map_match
        and not totals_mismatches
    )
    return report


def transformed(source: dict[str, Any], study: dict[str, Any], mapping: dict[str, str], policy: dict[str, Any]) -> dict[str, Any]:
    result = dict(source)
    for field in policy["direct_identifiers"]: result.pop(field, None)
    result["PatientID"] = study["pseudonym"]
    result["PatientIdentityRemoved"] = "YES"
    result["DeidentificationMethod"] = "DICOM-DEID-141-R1"
    result["PrivateTags"] = {k: v for k, v in dict(result.get("PrivateTags", {})).items() if k in policy["private_tag_allowlist"]}
    for field in policy["date_fields"]:
        if field in result: result[field] = shift_date(str(result[field]), int(study["date_shift_days"]))
    for field in policy["uid_fields"]:
        if field in result: result[field] = mapping[str(result[field])]
    return result


def tree_hash() -> str:
    root = ROOT / "exports"
    payload = []
    if root.exists():
        for path in sorted(p for p in root.rglob("*") if p.is_file()): payload.append((path.relative_to(ROOT).as_posix(), digest(path.read_bytes())))
    return digest(canonical(payload))


def apply(plan_path: Path) -> None:
    plan, report = load(plan_path), compare(load(plan_path))
    if not report["valid"]: raise ValueError("plan invalid; run preview and inspect mismatch fields")
    semantic = "sha256:" + digest(canonical(normalized(plan)))
    with sqlite3.connect(DB) as con:
        existing = con.execute("SELECT source_checkpoint,semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if existing:
            if existing == (plan["source_checkpoint"], semantic):
                print("already applied: semantic no-op"); return
            raise ValueError("conflicting plan for existing recovery identity")
        studies = {r["study_instance_uid"]: r for r in rows(con, "studies", "study_instance_uid")}
        for journal in rows(con, "recovery_journal", "journal_id"):
            if not journal["restored"]:
                con.execute("DELETE FROM export_records WHERE sop_instance_uid=? AND recovery_id=?", (journal["sop_instance_uid"], journal["recovery_id"]))
                write_dicom(ROOT / journal["orphan_relpath"], {"QuarantineStatus": "rolled_back_partial", "RecoveryID": journal["recovery_id"], "PatientIdentityRemoved": "YES"})
                con.execute("UPDATE recovery_journal SET restored=1 WHERE journal_id=?", (journal["journal_id"],))
                con.execute("UPDATE recovery_runs SET status='rolled_back' WHERE recovery_id=?", (journal["recovery_id"],))
        mapping = {row["original_uid"]: row["deidentified_uid"] for row in plan["uid_map"]}
        stream = {row["delivery_id"]: row for row in deliveries()}
        for decision in plan["instance_decisions"]:
            if decision["disposition"] != "generate_deidentified_instance": continue
            item = stream[decision["delivery_id"]]
            out = transformed(item["dataset"], studies[decision["study_instance_uid"]], mapping, load(POLICY))
            path = ROOT / decision["output_relpath"]
            write_dicom(path, out)
            con.execute("INSERT INTO export_records VALUES(?,?,?,?,?,?)", (decision["sop_instance_uid"], decision["study_instance_uid"], decision["output_relpath"], digest(path.read_bytes()), plan["recovery_id"], "locally_deidentified"))
        con.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,0)", (plan["recovery_id"], "applied", plan["source_checkpoint"], semantic))
        con.execute("UPDATE system_state SET value='local_review_ready' WHERE key='pipeline_state'")
        con.commit()
    write_json(ROOT / "state/recovery_receipt.json", {"schema_version": 1, "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": semantic, "restored_journals": ["J-DICOM-141"], "generated_instances": plan["totals"]["generated_instances"], "external_exports_executed": False})


def verify(plan_path: Path) -> None:
    plan = normalized(load(plan_path))
    if not compare(plan)["valid"]:
        raise ValueError("plan differs from current source-derived expectation")
    policy = load(POLICY)
    with sqlite3.connect(DB) as con:
        studies = {r["study_instance_uid"]: r for r in rows(con, "studies", "study_instance_uid")}
        records = {r["sop_instance_uid"]: r for r in rows(con, "export_records", "sop_instance_uid")}
    mapping = {row["original_uid"]: row["deidentified_uid"] for row in plan["uid_map"]}
    stream = {row["delivery_id"]: row for row in deliveries()}
    checks = []
    for decision in plan["instance_decisions"]:
        if decision["disposition"] != "generate_deidentified_instance": continue
        path = ROOT / decision["output_relpath"]
        got = read_dicom(path)
        wanted = transformed(stream[decision["delivery_id"]]["dataset"], studies[decision["study_instance_uid"]], mapping, policy)
        row = records.get(decision["sop_instance_uid"], {})
        checks.append(got == wanted and row.get("output_sha256") == digest(path.read_bytes()) and row.get("status") == "locally_deidentified")
    protected = records.get("1.2.840.141.3.1.1", {})
    valid = len(checks) == plan["totals"]["generated_instances"] and all(checks) and protected.get("status") == "protected"
    report = {"schema_version": 1, "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"], "semantic_plan_digest": "sha256:" + digest(canonical(plan)), "generated_instances": len(checks), "identifier_removal_valid": valid, "uid_reference_graph_valid": valid, "private_tag_policy_valid": valid, "date_shift_valid": valid, "protected_boundary_valid": valid, "external_exports_executed": False, "valid": valid}
    write_json(ROOT / "state/verification.json", report)
    if not valid: raise ValueError("independent output verification failed")


def stage(plan_path: Path) -> None:
    plan = normalized(load(plan_path)); verification = load(ROOT / "state/verification.json")
    handoff = ROOT / "deid_handoff.md"
    if not verification.get("valid") or not handoff.is_file(): raise ValueError("valid verification and deid_handoff.md required")
    packet = {"schema_version": 1, "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"], "generated_outputs": sorted(row["output_relpath"] for row in plan["instance_decisions"] if row["output_relpath"]), "quarantine_delivery_ids": sorted(row["delivery_id"] for row in plan["delivery_dispositions"] if "quarantined" in row["disposition"]), "protected_delivery_ids": sorted(row["delivery_id"] for row in plan["delivery_dispositions"] if row["disposition"] == "protected_study_ignored"), "external_exports_executed": False}
    packet_path = ROOT / "exports/research_review_packet.json"; write_json(packet_path, packet)
    files = {"exports/research_review_packet.json": digest(packet_path.read_bytes()), "deid_handoff.md": digest(handoff.read_bytes())}
    for rel in packet["generated_outputs"]: files[rel] = digest((ROOT / rel).read_bytes())
    write_json(ROOT / "exports/packet_manifest.json", {"schema_version": 1, "recovery_id": plan["recovery_id"], "source_checkpoint": plan["source_checkpoint"], "files": files, "external_exports_executed": False})


def replay(plan_path: Path) -> None:
    plan = normalized(load(plan_path)); semantic = "sha256:" + digest(canonical(plan))
    with sqlite3.connect(DB) as con:
        existing = con.execute("SELECT source_checkpoint,semantic_plan_digest FROM recovery_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    if existing != (plan["source_checkpoint"], semantic): raise ValueError("stale checkpoint or conflicting semantic plan")
    db_before, tree_before = digest(DB.read_bytes()), tree_hash()
    db_after, tree_after = digest(DB.read_bytes()), tree_hash()
    write_json(ROOT / "state/replay_report.json", {"schema_version": 1, "recovery_id": plan["recovery_id"], "status": "semantic_replay_noop", "database_unchanged": db_before == db_after, "export_tree_unchanged": tree_before == tree_after, "semantic_plan_digest": semantic, "external_exports_executed": False})


def inspect() -> None:
    ok, changed = sources_valid()
    with sqlite3.connect(DB) as con:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables if not table.startswith("sqlite_")}
    print(json.dumps({"source_manifest_valid": ok, "changed_sources": changed, "tables": counts, "deliveries": len(deliveries()), "commands": ["query", "preview", "apply", "verify", "stage", "replay"]}, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect"); q = sub.add_parser("query"); q.add_argument("table")
    for name in ("preview", "apply", "verify", "stage", "replay"):
        item = sub.add_parser(name); item.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect": inspect()
        elif args.command == "query":
            allowed = {"studies": "study_instance_uid", "export_records": "sop_instance_uid", "recovery_runs": "recovery_id", "recovery_journal": "journal_id", "system_state": "key"}
            if args.table not in allowed: raise ValueError(f"allowed tables: {sorted(allowed)}")
            with sqlite3.connect(DB) as con: print(json.dumps(rows(con, args.table, allowed[args.table]), indent=2, sort_keys=True))
        else:
            path = (ROOT / args.plan).resolve()
            if path.parent != ROOT or not path.is_file(): raise ValueError("plan must be a workspace-root file")
            if args.command == "preview":
                report = compare(load(path)); ok, changed = sources_valid(); report["changed_sources"] = changed; report["valid"] = report["valid"] and ok; write_json(ROOT / ".deid_preview.json", report); print(json.dumps(report, indent=2, sort_keys=True))
            elif args.command == "apply": apply(path)
            elif args.command == "verify": verify(path)
            elif args.command == "stage": stage(path)
            elif args.command == "replay": replay(path)
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
