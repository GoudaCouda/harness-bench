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
DB = ROOT / "state/configuration.db"
PLAN_FIELDS = {
    "schema_version", "recovery_id", "ecn_id", "source_checkpoint",
    "baseline_changes", "work_order_decisions", "external_actions_executed",
}
CHANGE_FIELDS = {
    "item_id", "from_revision", "to_revision", "where_used_path",
    "changed_line_no", "from_component", "from_component_revision",
    "to_component", "to_component_revision", "quantity",
    "approved_substitutes", "evidence_refs",
}
DECISION_FIELDS = {
    "work_order_id", "end_item", "serial_or_lot", "effectivity_basis",
    "effectivity_value", "effective", "status", "kit_state",
    "issued_component", "from_revision", "to_revision", "disposition",
    "local_mutations", "evidence_refs", "external_action",
}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must be one JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, table: str, order: str) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def source_manifest() -> tuple[dict[str, str], str]:
    manifest = load_json(ROOT / "policy/source_manifest.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict):
        raise ValueError("source manifest is malformed")
    changed = []
    for locator, expected in files.items():
        path = ROOT / str(locator)
        actual = sha(path.read_bytes()) if path.is_file() else "missing"
        if actual != expected:
            changed.append(str(locator))
    if changed:
        raise ValueError("immutable source mismatch: " + ", ".join(sorted(changed)))
    return {str(key): str(value) for key, value in files.items()}, sha(canonical(files))


def load_work_evidence() -> list[dict[str, Any]]:
    path = ROOT / "evidence/work_orders.jsonl"
    result = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed work-order evidence line {number}") from exc
        if not isinstance(row, dict) or not row.get("work_order_id"):
            raise ValueError(f"invalid work-order evidence line {number}")
        key = str(row["work_order_id"])
        if key in seen:
            raise ValueError(f"duplicate work-order evidence {key}")
        seen.add(key)
        result.append(row)
    return sorted(result, key=lambda row: str(row["work_order_id"]))


def baseline_snapshot(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    baseline = rows(connection, "baselines", "item_id, revision")
    items = rows(connection, "bom_items", "item_id, revision, line_no")
    work = {row["work_order_id"]: row for row in rows(connection, "work_orders", "work_order_id")}
    runs = {row["recovery_id"]: row for row in rows(connection, "ecn_runs", "recovery_id")}
    journal = rows(connection, "ecn_journal", "journal_id")
    for entry in journal:
        run = runs.get(entry["recovery_id"])
        if (
            not run
            or run["state"] not in {"interrupted", "committed", "staged_pending_review"}
            or entry["restored"]
        ):
            continue
        if entry["entity_type"] == "work_order":
            prior = json.loads(entry["before_json"])
            work[prior["work_order_id"]] = prior
        elif entry["entity_type"] == "baseline_insert":
            added = json.loads(entry["after_json"])
            baseline = [
                row for row in baseline
                if (row["item_id"], row["revision"]) != (added["item_id"], added["revision"])
            ]
            items = [
                row for row in items
                if (row["item_id"], row["revision"]) != (added["item_id"], added["revision"])
            ]
    return {
        "baselines": baseline,
        "bom_items": items,
        "work_orders": [work[key] for key in sorted(work)],
    }


def source_checkpoint() -> str:
    files, bundle_hash = source_manifest()
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        state = dict(connection.execute("SELECT key, value FROM system_state").fetchall())
        baseline = baseline_snapshot(connection)
    return sha(canonical({
        "immutable_source_hashes": files,
        "source_bundle_hash": bundle_hash,
        "source_revision": int(state["source_revision"]),
        "recovered_configuration_baseline": baseline,
    }))


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    changes = []
    for raw in plan.get("baseline_changes", []) if isinstance(plan.get("baseline_changes"), list) else []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        for key in ("approved_substitutes", "evidence_refs"):
            if isinstance(row.get(key), list):
                row[key] = sorted(set(str(value) for value in row[key]))
        changes.append(row)
    decisions = []
    for raw in plan.get("work_order_decisions", []) if isinstance(plan.get("work_order_decisions"), list) else []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        for key in ("local_mutations", "evidence_refs"):
            if isinstance(row.get(key), list):
                row[key] = sorted(set(str(value) for value in row[key]))
        decisions.append(row)
    result["baseline_changes"] = sorted(changes, key=lambda row: str(row.get("item_id")))
    result["work_order_decisions"] = sorted(decisions, key=lambda row: str(row.get("work_order_id")))
    return result


def plan_digest(plan: dict[str, Any]) -> str:
    return sha(canonical(normalized_plan(plan)))


def source_context() -> dict[str, Any]:
    policy = load_json(ROOT / "policy/ecn_policy.json")
    ecn = load_json(ROOT / "evidence/engineering_change.json")
    evidence_work = load_work_evidence()
    if ecn.get("approval_state") != policy.get("approval_state_required"):
        raise ValueError("ECN is not approved")
    if ecn.get("ecn_id") != policy.get("ecn_id"):
        raise ValueError("ECN identity mismatch")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        base = baseline_snapshot(connection)
    db_work = {row["work_order_id"]: row for row in base["work_orders"]}
    for row in evidence_work:
        current = db_work.get(row["work_order_id"])
        compared = {key: current.get(key) for key in row} if current else None
        if compared != row:
            raise ValueError(f"work-order source identity mismatch for {row['work_order_id']}")
    items = base["bom_items"]
    revmap = policy["revision_map"]
    old_to_new = {item: values for item, values in revmap.items()}
    child_of: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for line in items:
        if line["item_id"] in old_to_new and line["revision"] == old_to_new[line["item_id"]]["from"]:
            child_of.setdefault(line["component_id"], []).append((line["item_id"], line))
    direct = str(ecn["direct_assembly"])
    paths = {direct: direct}
    queue = [direct]
    while queue:
        child = queue.pop(0)
        for parent, _line in child_of.get(child, []):
            if parent not in paths:
                paths[parent] = parent + ">" + paths[child]
                queue.append(parent)
    if set(paths) != set(revmap):
        raise ValueError("revision map does not match released where-used closure")
    return {
        "policy": policy,
        "change": ecn,
        "work_evidence": evidence_work,
        "bom_items": items,
        "revision_map": revmap,
        "where_used_paths": paths,
        "direct_assembly": direct,
    }


def baseline_candidate_checks(
    candidate: dict[str, Any], item_id: str, context: dict[str, Any]
) -> dict[str, object]:
    policy = context["policy"]
    revisions = context["revision_map"][item_id]
    path = context["where_used_paths"][item_id]
    source_lines = [
        row for row in context["bom_items"]
        if row["item_id"] == item_id and row["revision"] == revisions["from"]
    ]
    component = policy["component_change"]
    if item_id == context["direct_assembly"]:
        selected = [
            row for row in source_lines
            if row["component_id"] == component["from_part"]
            and row["substitute_for"] is None
        ]
        if len(selected) != 1 or selected[0]["quantity"] != component["quantity"]:
            raise ValueError("direct component line is ambiguous")
        line = selected[0]
        child = component["from_part"]
        next_component = component["to_part"]
        next_revision = line["component_revision"]
        substitutes = policy["approved_substitutes"].get(next_component, [])
    else:
        children = [
            part for part in context["revision_map"]
            if path.split(">", 1)[1].startswith(part)
        ]
        if len(children) != 1:
            raise ValueError(f"ambiguous changed child for {item_id}")
        child = children[0]
        selected = [
            row for row in source_lines
            if row["component_id"] == child
            and row["component_revision"] == context["revision_map"][child]["from"]
        ]
        if len(selected) != 1:
            raise ValueError(f"released where-used line missing for {item_id}")
        line = selected[0]
        next_component = child
        next_revision = context["revision_map"][child]["to"]
        substitutes = []
    evidence = candidate.get("evidence_refs")
    evidence_set = set(evidence) if isinstance(evidence, list) else set()
    fields = {
        "item_id": candidate.get("item_id") == item_id,
        "from_revision": candidate.get("from_revision") == revisions["from"],
        "to_revision": candidate.get("to_revision") == revisions["to"],
        "where_used_path": candidate.get("where_used_path") == path,
        "changed_line_no": candidate.get("changed_line_no") == line["line_no"],
        "from_component": candidate.get("from_component") == child,
        "from_component_revision": (
            candidate.get("from_component_revision") == line["component_revision"]
        ),
        "to_component": candidate.get("to_component") == next_component,
        "to_component_revision": candidate.get("to_component_revision") == next_revision,
        "quantity": candidate.get("quantity") == line["quantity"],
        "approved_substitutes": sorted(set(candidate.get("approved_substitutes", [])))
        == sorted(substitutes)
        if isinstance(candidate.get("approved_substitutes"), list)
        else False,
        "evidence_refs": evidence_set == {
            "evidence/engineering_change.json#ECN-442",
            f"policy/ecn_policy.json#revision_map/{item_id}",
            f"state/configuration.db#bom_items/{item_id}@{revisions['from']}/{line['line_no']}",
        },
    }
    return {
        "fields": fields,
        "evidence_categories": {
            "approved_change": "evidence/engineering_change.json#ECN-442" in evidence_set,
            "revision_authority": (
                f"policy/ecn_policy.json#revision_map/{item_id}" in evidence_set
            ),
            "released_bom_line": (
                f"state/configuration.db#bom_items/{item_id}@{revisions['from']}/{line['line_no']}"
                in evidence_set
            ),
        },
    }


def work_order_candidate_checks(
    candidate: dict[str, Any], source: dict[str, Any], context: dict[str, Any]
) -> dict[str, object]:
    policy = context["policy"]
    effect = policy["effectivity"][source["end_item"]]
    effective = str(source["serial_or_lot"]) >= str(effect["from"])
    approved = {
        policy["component_change"]["to_part"],
        *policy["approved_substitutes"].get(
            policy["component_change"]["to_part"], []
        ),
    }
    if source["status"] == "assembled":
        disposition, mutations = "preserve_as_built", []
    elif not effective:
        disposition, mutations = "preserve_pre_effectivity_kit", []
    elif source["kit_state"] == "issued" and source["issued_component"] in approved:
        disposition = "accept_approved_substitute_new_baseline"
        mutations = ["baseline_revision", "ecn_disposition"]
    elif source["kit_state"] == "issued":
        disposition = "hold_and_rekit"
        mutations = ["baseline_revision", "ecn_disposition"]
    else:
        disposition = "adopt_new_baseline"
        mutations = ["baseline_revision", "ecn_disposition"]
    target_revision = context["revision_map"][source["end_item"]]["to"]
    evidence = candidate.get("evidence_refs")
    evidence_set = set(evidence) if isinstance(evidence, list) else set()
    work_id = source["work_order_id"]
    fields = {
        "work_order_id": candidate.get("work_order_id") == work_id,
        "end_item": candidate.get("end_item") == source["end_item"],
        "serial_or_lot": candidate.get("serial_or_lot") == source["serial_or_lot"],
        "effectivity_basis": candidate.get("effectivity_basis") == effect["basis"],
        "effectivity_value": candidate.get("effectivity_value") == effect["from"],
        "effective": candidate.get("effective") is effective,
        "status": candidate.get("status") == source["status"],
        "kit_state": candidate.get("kit_state") == source["kit_state"],
        "issued_component": candidate.get("issued_component") == source["issued_component"],
        "from_revision": candidate.get("from_revision") == source["baseline_revision"],
        "to_revision": candidate.get("to_revision")
        == (target_revision if effective else source["baseline_revision"]),
        "disposition": candidate.get("disposition") == disposition,
        "local_mutations": sorted(set(candidate.get("local_mutations", [])))
        == sorted(mutations)
        if isinstance(candidate.get("local_mutations"), list)
        else False,
        "evidence_refs": evidence_set == {
            f"evidence/work_orders.jsonl#{work_id}",
            f"policy/ecn_policy.json#effectivity/{source['end_item']}",
            f"state/configuration.db#work_orders/{work_id}",
        },
        "external_action": candidate.get("external_action") == "none",
    }
    return {
        "fields": fields,
        "evidence_categories": {
            "protected_work_order": f"evidence/work_orders.jsonl#{work_id}" in evidence_set,
            "effectivity_policy": (
                f"policy/ecn_policy.json#effectivity/{source['end_item']}" in evidence_set
            ),
            "database_identity": (
                f"state/configuration.db#work_orders/{work_id}" in evidence_set
            ),
        },
    }


def all_checks_pass(value: object) -> bool:
    if isinstance(value, dict):
        return all(all_checks_pass(child) for child in value.values())
    return value is True


def validate(plan: dict[str, Any]) -> tuple[bool, dict[str, object]]:
    context = source_context()
    candidate = normalized_plan(plan)
    exact_schema = (
        set(plan) == PLAN_FIELDS
        and isinstance(plan.get("baseline_changes"), list)
        and isinstance(plan.get("work_order_decisions"), list)
        and all(isinstance(row, dict) and set(row) == CHANGE_FIELDS for row in plan.get("baseline_changes", []))
        and all(isinstance(row, dict) and set(row) == DECISION_FIELDS for row in plan.get("work_order_decisions", []))
    )
    changes = candidate.get("baseline_changes", [])
    change_by_id = {
        str(row.get("item_id")): row for row in changes if isinstance(row, dict)
    }
    expected_items = set(context["where_used_paths"])
    work = candidate.get("work_order_decisions", [])
    work_by_id = {
        str(row.get("work_order_id")): row for row in work if isinstance(row, dict)
    }
    source_work = {
        row["work_order_id"]: row for row in context["work_evidence"]
    }
    checks: dict[str, object] = {
        "exact_schema": exact_schema,
        "approved_ecn_identity": (
            candidate.get("schema_version") == 1
            and candidate.get("recovery_id") == context["policy"]["recovery_id"]
            and candidate.get("ecn_id") == context["policy"]["ecn_id"]
        ),
        "fresh_source_checkpoint": candidate.get("source_checkpoint") == source_checkpoint(),
        "baseline_changes": {
            "complete_object_set": (
                len(changes) == len(change_by_id)
                and set(change_by_id) == expected_items
            ),
            "objects": {
                item_id: baseline_candidate_checks(
                    change_by_id.get(item_id, {}), item_id, context
                )
                for item_id in sorted(expected_items)
            },
        },
        "work_order_decisions": {
            "complete_object_set": (
                len(work) == len(work_by_id)
                and set(work_by_id) == set(source_work)
            ),
            "objects": {
                work_id: work_order_candidate_checks(
                    work_by_id.get(work_id, {}), source_work[work_id], context
                )
                for work_id in sorted(source_work)
            },
        },
        "external_boundary": candidate.get("external_actions_executed") is False,
    }
    return all_checks_pass(checks), checks


def target_rows(plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        baseline = baseline_snapshot(connection)
    baselines = list(baseline["baselines"])
    items = list(baseline["bom_items"])
    work = {row["work_order_id"]: dict(row) for row in baseline["work_orders"]}
    for change in normalized_plan(plan)["baseline_changes"]:
        baselines.append({
            "item_id": change["item_id"], "revision": change["to_revision"],
            "status": "pending_configuration_review", "ecn_id": plan["ecn_id"],
        })
        source = [row for row in items if row["item_id"] == change["item_id"] and row["revision"] == change["from_revision"]]
        for original in source:
            row = dict(original)
            row["revision"] = change["to_revision"]
            if row["line_no"] == change["changed_line_no"]:
                row["component_id"] = change["to_component"]
                row["component_revision"] = change["to_component_revision"]
            # Remove obsolete substitute and add only approved replacement below.
            if change["item_id"] == "ACTUATOR-MODULE" and row["substitute_for"] == change["from_component"]:
                continue
            items.append(row)
        if change["item_id"] == "ACTUATOR-MODULE":
            for offset, substitute in enumerate(change["approved_substitutes"], 1):
                items.append({
                    "item_id": change["item_id"], "revision": change["to_revision"],
                    "line_no": change["changed_line_no"] + offset,
                    "component_id": substitute, "component_revision": "1",
                    "quantity": change["quantity"], "substitute_for": change["to_component"],
                })
    for decision in normalized_plan(plan)["work_order_decisions"]:
        row = work[decision["work_order_id"]]
        if decision["local_mutations"]:
            row["baseline_revision"] = decision["to_revision"]
            row["ecn_disposition"] = decision["disposition"]
            row["version"] = int(row["version"]) + 1
    return (
        sorted(baselines, key=lambda row: (row["item_id"], row["revision"])),
        sorted(items, key=lambda row: (row["item_id"], row["revision"], row["line_no"])),
        [work[key] for key in sorted(work)],
    )


def logical_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "baselines": rows(connection, "baselines", "item_id, revision"),
        "bom_items": rows(connection, "bom_items", "item_id, revision, line_no"),
        "work_orders": rows(connection, "work_orders", "work_order_id"),
        "system_state": rows(connection, "system_state", "key"),
    }


def logical_hash(connection: sqlite3.Connection) -> str:
    return sha(canonical(logical_snapshot(connection)))


def restore_interrupted(connection: sqlite3.Connection) -> None:
    runs = {row["recovery_id"]: row for row in rows(connection, "ecn_runs", "recovery_id")}
    for entry in rows(connection, "ecn_journal", "journal_id"):
        run = runs.get(entry["recovery_id"])
        if not run or run["state"] != "interrupted" or entry["restored"]:
            continue
        if entry["entity_type"] == "work_order":
            prior = json.loads(entry["before_json"])
            connection.execute(
                "UPDATE work_orders SET end_item=?, serial_or_lot=?, status=?, baseline_revision=?, kit_state=?, issued_component=?, ecn_disposition=?, version=? WHERE work_order_id=?",
                (prior["end_item"], prior["serial_or_lot"], prior["status"], prior["baseline_revision"], prior["kit_state"], prior["issued_component"], prior["ecn_disposition"], prior["version"], prior["work_order_id"]),
            )
        elif entry["entity_type"] == "baseline_insert":
            added = json.loads(entry["after_json"])
            connection.execute("DELETE FROM baselines WHERE item_id=? AND revision=?", (added["item_id"], added["revision"]))
        connection.execute("UPDATE ecn_journal SET restored=1 WHERE journal_id=?", (entry["journal_id"],))
    connection.execute("UPDATE ecn_runs SET state='restored' WHERE state='interrupted'")


def inspect() -> int:
    source_manifest()
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        value = {
            "source_revision": dict(connection.execute("SELECT key, value FROM system_state").fetchall())["source_revision"],
            "released_baselines": rows(connection, "baselines", "item_id, revision"),
            "interrupted_runs": [row for row in rows(connection, "ecn_runs", "recovery_id") if row["state"] == "interrupted"],
            "unrestored_journal_entries": sum(not row["restored"] for row in rows(connection, "ecn_journal", "journal_id")),
            "source_checkpoint": source_checkpoint(),
        }
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def query(entity: str) -> int:
    if entity == "policy":
        value: object = load_json(ROOT / "policy/ecn_policy.json")
    elif entity == "change":
        value = load_json(ROOT / "evidence/engineering_change.json")
    elif entity == "work-orders":
        value = load_work_evidence()
    else:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
            tables = {"bom": ("bom_items", "item_id, revision, line_no"), "journal": ("ecn_journal", "journal_id")}
            table, order = tables[entity]
            value = rows(connection, table, order)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def impact(ecn_id: str) -> int:
    context = source_context()
    if ecn_id != context["policy"]["ecn_id"]:
        print(json.dumps({"status": "not_found", "ecn_id": ecn_id}))
        return 2
    value = {
        "ecn_id": ecn_id,
        "where_used": [
            {
                "item_id": item_id,
                "from_revision": context["revision_map"][item_id]["from"],
                "to_revision": context["revision_map"][item_id]["to"],
                "where_used_path": context["where_used_paths"][item_id],
            }
            for item_id in sorted(context["where_used_paths"])
        ],
        "candidate_work_orders": [
            {
                key: row[key]
                for key in (
                    "work_order_id", "end_item", "serial_or_lot", "status",
                    "kit_state", "issued_component",
                )
            }
            for row in context["work_evidence"]
        ],
        "warning": "impact is evidence discovery only; preview validates effectivity and disposition",
    }
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def preview(path: Path) -> int:
    try:
        plan = load_json(path)
        ok, checks = validate(plan)
        value = {"status": "pass" if ok else "fail", "checks": checks, "semantic_plan_sha256": plan_digest(plan) if ok else None}
    except ValueError as exc:
        ok = False
        value = {"status": "fail", "error": str(exc)}
    write_json(ROOT / ".ecn_preview.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if ok else 2


def apply(path: Path) -> int:
    plan = load_json(path)
    digest = plan_digest(plan)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as read_connection:
        prior = read_connection.execute(
            "SELECT semantic_plan_sha256 FROM ecn_runs WHERE recovery_id=?",
            (plan.get("recovery_id"),),
        ).fetchone()
    if prior and prior[0] != digest:
        print(json.dumps({
            "status": "conflict",
            "error": "same recovery identity has a different semantic plan",
        }))
        return 3
    ok, checks = validate(plan)
    if not ok:
        print(json.dumps({"status": "rejected", "checks": checks}, indent=2))
        return 2
    targets = target_rows(plan)
    with sqlite3.connect(DB) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute("SELECT semantic_plan_sha256, state FROM ecn_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        if existing:
            if existing[0] == digest and existing[1] in {"committed", "staged_pending_review"}:
                print(json.dumps({"status": "idempotent_noop", "semantic_plan_sha256": digest}))
                return 0
            raise ValueError("conflicting recovery identity already exists")
        restore_interrupted(connection)
        baseline_before = rows(connection, "baselines", "item_id, revision")
        work_before = {row["work_order_id"]: row for row in rows(connection, "work_orders", "work_order_id")}
        for row in targets[0]:
            if row not in baseline_before:
                connection.execute("INSERT INTO baselines VALUES (?, ?, ?, ?)", tuple(row[key] for key in ("item_id", "revision", "status", "ecn_id")))
                connection.execute(
                    "INSERT INTO ecn_journal(recovery_id,entity_type,entity_key,before_json,after_json,restored) VALUES (?,?,?,?,?,0)",
                    (plan["recovery_id"], "baseline_insert", f"{row['item_id']}@{row['revision']}", "null", json.dumps(row, sort_keys=True)),
                )
        current_items = rows(connection, "bom_items", "item_id, revision, line_no")
        for row in targets[1]:
            if row not in current_items:
                connection.execute("INSERT INTO bom_items VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(row[key] for key in ("item_id", "revision", "line_no", "component_id", "component_revision", "quantity", "substitute_for")))
        for after in targets[2]:
            before = work_before[after["work_order_id"]]
            if after != before:
                connection.execute(
                    "UPDATE work_orders SET baseline_revision=?, ecn_disposition=?, version=? WHERE work_order_id=?",
                    (after["baseline_revision"], after["ecn_disposition"], after["version"], after["work_order_id"]),
                )
                connection.execute(
                    "INSERT INTO ecn_journal(recovery_id,entity_type,entity_key,before_json,after_json,restored) VALUES (?,?,?,?,?,0)",
                    (plan["recovery_id"], "work_order", after["work_order_id"], json.dumps(before, sort_keys=True), json.dumps(after, sort_keys=True)),
                )
        current_hash = logical_hash(connection)
        connection.execute(
            "INSERT INTO ecn_runs VALUES (?, ?, ?, ?, 'committed', ?)",
            (plan["recovery_id"], plan["ecn_id"], plan["source_checkpoint"], digest, current_hash),
        )
        connection.commit()
    print(json.dumps({"status": "committed", "semantic_plan_sha256": digest, "logical_db_sha256": current_hash}, indent=2))
    return 0


def verification_payload(plan: dict[str, Any]) -> dict[str, Any]:
    digest = plan_digest(plan)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        run = connection.execute("SELECT * FROM ecn_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
        names = [row[1] for row in connection.execute("PRAGMA table_info(ecn_runs)")]
        run_value = dict(zip(names, run, strict=True)) if run else {}
        target = target_rows(plan)
        checks = {
            "run_committed_once": run_value.get("state") in {"committed", "staged_pending_review"},
            "source_checkpoint_bound": run_value.get("source_checkpoint") == plan["source_checkpoint"] == source_checkpoint(),
            "semantic_plan_bound": run_value.get("semantic_plan_sha256") == digest,
            "interrupted_journal_restored": not connection.execute("SELECT 1 FROM ecn_runs WHERE state='interrupted'").fetchone() and not connection.execute("SELECT 1 FROM ecn_journal WHERE recovery_id='ECNREC-20260818-442-PARTIAL' AND restored=0").fetchone(),
            "baseline_revisions_exact": rows(connection, "baselines", "item_id, revision") == target[0],
            "where_used_rows_exact": rows(connection, "bom_items", "item_id, revision, line_no") == target[1],
            "work_order_boundaries_exact": rows(connection, "work_orders", "work_order_id") == target[2],
            "logical_database_bound": run_value.get("logical_db_sha256") == logical_hash(connection),
        }
        logical = logical_hash(connection)
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "ecn_id": plan["ecn_id"], "recovery_id": plan["recovery_id"],
        "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_sha256": digest, "logical_db_sha256": logical,
        "checks": checks, "external_actions_executed": False,
    }


def verify(path: Path) -> int:
    plan = load_json(path)
    value = verification_payload(plan)
    write_json(ROOT / "state/verification.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value["status"] == "pass" else 2


def stage(path: Path) -> int:
    plan = load_json(path)
    verification = verification_payload(plan)
    verification_path = ROOT / "state/verification.json"
    if verification.get("status") != "pass" or not verification_path.is_file() or load_json(verification_path) != verification:
        print(json.dumps({"status": "rejected", "error": "fresh verification required"}))
        return 2
    unsigned = {
        "receipt_type": "internal_configuration_change_stage",
        "ecn_id": plan["ecn_id"], "recovery_id": plan["recovery_id"],
        "stage_state": "pending_configuration_review",
        "source_checkpoint": plan["source_checkpoint"],
        "semantic_plan_sha256": plan_digest(plan),
        "logical_db_sha256": verification["logical_db_sha256"],
        "verification_sha256": sha(verification_path.read_bytes()),
        "release_executed": False, "shop_floor_change_executed": False,
        "supplier_order_placed": False,
    }
    receipt = {**unsigned, "stage_token": sha(canonical(unsigned))}
    write_json(ROOT / "state/internal_change_receipt.json", receipt)
    with sqlite3.connect(DB) as connection:
        connection.execute("UPDATE ecn_runs SET state='staged_pending_review' WHERE recovery_id=?", (plan["recovery_id"],))
        connection.commit()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def replay(path: Path) -> int:
    plan = load_json(path)
    ok, checks = validate(plan)
    if not ok:
        print(json.dumps({"status": "rejected", "checks": checks}, indent=2))
        return 2
    digest = plan_digest(plan)
    receipt_path = ROOT / "state/internal_change_receipt.json"
    before_db = sha(DB.read_bytes())
    before_receipt = sha(receipt_path.read_bytes()) if receipt_path.is_file() else "missing"
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        run = connection.execute("SELECT semantic_plan_sha256,state FROM ecn_runs WHERE recovery_id=?", (plan["recovery_id"],)).fetchone()
    if not run or run[0] != digest:
        print(json.dumps({"status": "rejected", "error": "recovery identity conflict or missing commit"}))
        return 2
    if run[1] != "staged_pending_review" or before_receipt == "missing":
        print(json.dumps({"status": "rejected", "error": "internal stage is incomplete"}))
        return 2
    after_db = sha(DB.read_bytes())
    after_receipt = sha(receipt_path.read_bytes())
    value = {
        "status": "idempotent_replay", "ecn_id": plan["ecn_id"],
        "semantic_plan_sha256": digest,
        "database_byte_stable": before_db == after_db,
        "stage_receipt_byte_stable": before_receipt == after_receipt,
        "external_actions_executed": False,
    }
    write_json(ROOT / "state/replay_report.json", value)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value["database_byte_stable"] and value["stage_receipt_byte_stable"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Guarded ECN configuration recovery controller")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    query_parser = commands.add_parser("query")
    query_parser.add_argument("entity", choices=("policy", "change", "work-orders", "bom", "journal"))
    impact_parser = commands.add_parser("impact")
    impact_parser.add_argument("ecn_id", nargs="?")
    impact_parser.add_argument("--ecn", dest="ecn_option")
    for command in ("preview", "apply", "verify", "stage", "replay"):
        child = commands.add_parser(command)
        child.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect()
        if args.command == "query":
            return query(args.entity)
        if args.command == "impact":
            if args.ecn_id and args.ecn_option and args.ecn_id != args.ecn_option:
                raise ValueError("conflicting positional ECN and --ecn values")
            ecn_id = args.ecn_id or args.ecn_option
            if not ecn_id:
                raise ValueError("impact requires ECN_ID or --ecn ECN_ID")
            return impact(ecn_id)
        return globals()[args.command](args.plan)
    except (OSError, UnicodeError, ValueError, sqlite3.Error, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
