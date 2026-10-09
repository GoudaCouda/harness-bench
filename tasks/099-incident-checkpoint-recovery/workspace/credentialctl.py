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
DB = ROOT / "state/credentials.db"
POLICY = ROOT / "policy/rotation_policy.json"
MANIFEST = ROOT / "policy/source_manifest.json"
SCOPE = ROOT / "evidence/incident_scope.json"
VALIDATION = ROOT / "evidence/validation.jsonl"
CHECKPOINT = ROOT / "state/stale_checkpoint.json"

PLAN_FIELDS = {
    "schema_version", "recovery_id", "source_checkpoint", "incident_id",
    "account_decisions", "journal_actions", "external_actions_executed",
}
ACCOUNT_FIELDS = {
    "account_id", "classification", "checkpoint_relation", "current_version",
    "target_version", "action", "evidence_refs",
}
JOURNAL_FIELDS = {"journal_id", "table_name", "record_id", "action"}


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_regular(path: Path, max_bytes: int = 8_000_000) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.relative_to(ROOT)} must be a regular local file")
    if path.stat().st_size > max_bytes:
        raise ValueError(f"{path.relative_to(ROOT)} exceeds the size limit")


def candidate_path(raw: str) -> Path:
    relative = Path(raw.replace("\\", "/"))
    if relative.is_absolute() or len(relative.parts) != 1 or relative.name != raw:
        raise ValueError("plan must be one workspace-root filename")
    path = ROOT / relative
    safe_regular(path, 1_000_000)
    return path


def output_path(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("unsafe output path")
    parent = ROOT
    for part in path.parts[:-1]:
        parent = parent / part
        if parent.exists() and parent.is_symlink():
            raise ValueError(f"{parent.relative_to(ROOT)} must not be a symlink")
        parent.mkdir(exist_ok=True)
    target = ROOT / path
    if target.is_symlink():
        raise ValueError(f"{relative} must not be a symlink")
    return target


def write_json(relative: str, value: object) -> None:
    output_path(relative).write_bytes(canonical(value))


def read_json(path: Path) -> dict[str, Any]:
    safe_regular(path, 1_000_000)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    safe_regular(path, 1_000_000)
    result = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{number} must contain an object")
        result.append(value)
    return result


def table_rows(
    connection: sqlite3.Connection, table: str, order: str
) -> list[dict[str, Any]]:
    cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {order}")
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def database_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "accounts": table_rows(connection, "accounts", "account_id"),
        "markers": table_rows(connection, "durable_markers", "account_id"),
        "queue": table_rows(connection, "rotation_queue", "queue_id"),
        "receipts": table_rows(connection, "decision_receipts", "recovery_id,account_id"),
        "runs": table_rows(connection, "recovery_runs", "recovery_id"),
        "journal": table_rows(connection, "recovery_journal", "journal_id"),
        "system": dict(connection.execute("SELECT key,value FROM system_state")),
    }


def recovered_base(snapshot: dict[str, Any], recovery_id: str) -> dict[str, Any]:
    accounts = {row["account_id"]: dict(row) for row in snapshot["accounts"]}
    queue = {
        row["queue_id"]: dict(row)
        for row in snapshot["queue"]
        if row["requested_by_recovery"] != recovery_id
    }
    recoverable = {
        row["recovery_id"]
        for row in snapshot["runs"]
        if row["status"] in {"interrupted", "rolled_back"}
    }
    for row in snapshot["journal"]:
        if row["recovery_id"] not in recoverable:
            continue
        before = json.loads(row["before_json"]) if row["before_json"] else None
        target = accounts if row["table_name"] == "accounts" else queue
        if before is None:
            target.pop(row["record_id"], None)
        else:
            target[row["record_id"]] = before
    return {
        "accounts": [accounts[key] for key in sorted(accounts)],
        "queue": [queue[key] for key in sorted(queue)],
        "journal": snapshot["journal"],
        "markers": snapshot["markers"],
        "system": snapshot["system"],
    }


def source_hashes() -> tuple[dict[str, str], bool]:
    manifest = read_json(MANIFEST).get("files", {})
    if not isinstance(manifest, dict):
        return {}, False
    actual: dict[str, str] = {}
    valid = True
    for relative, expected_hash in manifest.items():
        path = ROOT / str(relative)
        try:
            safe_regular(path, 1_000_000)
            actual[str(relative)] = digest(path.read_bytes())
        except (OSError, ValueError):
            valid = False
            continue
        valid &= actual[str(relative)] == expected_hash
    return actual, valid


def normalized_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = dict(plan)
    values = plan.get("account_decisions", [])
    if not isinstance(values, list):
        values = []
    decisions = []
    for value in values:
        if not isinstance(value, dict):
            continue
        row = dict(value)
        refs = row.get("evidence_refs")
        if isinstance(refs, list) and all(isinstance(item, str) for item in refs):
            row["evidence_refs"] = sorted(set(refs))
        decisions.append(row)
    result["account_decisions"] = sorted(
        decisions, key=lambda row: str(row.get("account_id"))
    )
    journal = plan.get("journal_actions", [])
    if not isinstance(journal, list):
        journal = []
    result["journal_actions"] = sorted(
        [dict(row) for row in journal if isinstance(row, dict)],
        key=lambda row: str(row.get("journal_id")),
    )
    return result


def source_context(connection: sqlite3.Connection) -> dict[str, Any]:
    policy = read_json(POLICY)
    scope = read_json(SCOPE)
    checkpoint = read_json(CHECKPOINT)
    validations = read_jsonl(VALIDATION)
    snapshot = database_snapshot(connection)
    base = recovered_base(snapshot, str(policy.get("recovery_id", "")))
    hashes, sources_valid = source_hashes()
    latest_validation: dict[str, dict[str, Any]] = {}
    for row in validations:
        account_id = str(row.get("account_id", ""))
        if int(row.get("sequence", -1)) > int(
            latest_validation.get(account_id, {}).get("sequence", -1)
        ):
            latest_validation[account_id] = row
    checkpoint_rows = {
        str(row["account_id"]): row for row in checkpoint.get("accounts", [])
    }
    source_checkpoint = digest(
        canonical(
            {
                "source_hashes": hashes,
                "source_revision": int(base["system"]["source_revision"]),
                "accounts": base["accounts"],
                "markers": base["markers"],
                "checkpoint": checkpoint,
                "scope": scope,
            }
        )
    )
    return {
        "policy": policy,
        "scope": scope,
        "checkpoint": checkpoint,
        "snapshot": snapshot,
        "base": base,
        "sources_valid": sources_valid,
        "latest_validation": latest_validation,
        "checkpoint_rows": checkpoint_rows,
        "source_checkpoint": source_checkpoint,
    }


def account_candidate_checks(
    candidate: dict[str, Any], scoped: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    account_id = str(scoped["account_id"])
    accounts = {row["account_id"]: row for row in context["base"]["accounts"]}
    markers = {row["account_id"]: row for row in context["base"]["markers"]}
    account = accounts[account_id]
    target_version = int(scoped.get("target_version") or account["durable_version"])
    marker = markers.get(account_id)
    completed = bool(
        scoped["compromised"]
        and marker
        and marker["incident_id"] == context["policy"]["incident_id"]
        and int(marker["target_version"]) == target_version
        and int(account["durable_version"]) == target_version
        and account["status"] == "active"
    )
    if completed:
        classification, action = "completed_durable", "preserve_committed"
    elif scoped["compromised"]:
        classification, action = "pending_rotation", "queue_single_future_rotation"
    else:
        classification, action = "preserved_clean", "preserve_unchanged"
        target_version = int(account["durable_version"])
    checkpoint = context["checkpoint_rows"].get(account_id)
    checkpoint_complete = bool(checkpoint and checkpoint.get("completed") is True)
    if completed:
        relation = (
            "checkpoint_agrees_completed"
            if checkpoint_complete and int(checkpoint.get("version", -1)) == target_version
            else "checkpoint_omits_durable_completion"
        )
    elif classification == "pending_rotation":
        relation = (
            "checkpoint_falsely_completed"
            if checkpoint_complete
            else "checkpoint_agrees_pending" if checkpoint else "checkpoint_missing_pending"
        )
    else:
        relation = (
            "checkpoint_misclassifies_clean" if checkpoint else "checkpoint_clean_absent"
        )
    refs = candidate.get("evidence_refs")
    refs_valid = isinstance(refs, list) and all(isinstance(item, str) for item in refs)
    ref_set = set(refs) if refs_valid else set()
    scope_ref = f"evidence/incident_scope.json#accounts/{account_id}"
    account_ref = f"state/credentials.db#accounts/{account_id}"
    required_refs = {scope_ref, account_ref}
    categories = {
        "incident_scope": scope_ref in ref_set,
        "recovered_account": account_ref in ref_set,
        "stale_checkpoint": checkpoint is None,
        "durable_marker": not completed,
        "latest_validation": account_id not in context["latest_validation"],
        "recovery_journal": True,
    }
    if checkpoint:
        locator = f"state/stale_checkpoint.json#accounts/{account_id}"
        required_refs.add(locator)
        categories["stale_checkpoint"] = locator in ref_set
    if completed:
        locator = f"state/credentials.db#durable_markers/{account_id}"
        required_refs.add(locator)
        categories["durable_marker"] = locator in ref_set
    validation = context["latest_validation"].get(account_id)
    if validation:
        locator = f"evidence/validation.jsonl#{validation['validation_id']}"
        required_refs.add(locator)
        categories["latest_validation"] = locator in ref_set
    journals = [
        row for row in context["base"]["journal"] if row["record_id"] == account_id
    ]
    if journals:
        locators = {
            f"state/credentials.db#recovery_journal/{row['journal_id']}"
            for row in journals
        }
        required_refs.update(locators)
        categories["recovery_journal"] = locators.issubset(ref_set)
    return {
        "fields": {
            "exact_schema": set(candidate) == ACCOUNT_FIELDS,
            "account_id": candidate.get("account_id") == account_id,
            "classification": candidate.get("classification") == classification,
            "checkpoint_relation": candidate.get("checkpoint_relation") == relation,
            "current_version": candidate.get("current_version")
            == int(account["durable_version"]),
            "target_version": candidate.get("target_version") == target_version,
            "action": candidate.get("action") == action,
            "evidence_refs": refs_valid and ref_set == required_refs,
        },
        "evidence_categories": categories,
    }


def journal_candidate_checks(
    candidate: dict[str, Any], source: dict[str, Any]
) -> dict[str, bool]:
    return {
        "exact_schema": set(candidate) == JOURNAL_FIELDS,
        "journal_id": candidate.get("journal_id") == source["journal_id"],
        "table_name": candidate.get("table_name") == source["table_name"],
        "record_id": candidate.get("record_id") == source["record_id"],
        "action": candidate.get("action")
        == ("restore_before_image" if source["before_json"] else "remove_partial_insert"),
    }


def all_checks_pass(value: object) -> bool:
    if isinstance(value, dict):
        return all(all_checks_pass(child) for child in value.values())
    return value is True


def validate_candidate(
    plan: dict[str, Any], context: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    raw_decisions = plan.get("account_decisions", [])
    if not isinstance(raw_decisions, list):
        raw_decisions = []
    decisions = {
        str(row.get("account_id")): row
        for row in raw_decisions
        if isinstance(row, dict)
    }
    scoped = {
        str(row["account_id"]): row for row in context["scope"].get("accounts", [])
    }
    raw_journal = plan.get("journal_actions", [])
    if not isinstance(raw_journal, list):
        raw_journal = []
    journal = {
        str(row.get("journal_id")): row
        for row in raw_journal
        if isinstance(row, dict)
    }
    recoverable = {
        row["recovery_id"]
        for row in context["snapshot"]["runs"]
        if row["status"] in {"interrupted", "rolled_back"}
    }
    source_journal = {
        row["journal_id"]: row
        for row in context["base"]["journal"]
        if row["recovery_id"] in recoverable
    }
    checks = {
        "schema": {
            "exact_top_level": set(plan) == PLAN_FIELDS,
            "account_rows_are_objects": (
                isinstance(plan.get("account_decisions"), list)
                and all(isinstance(row, dict) for row in plan["account_decisions"])
            ),
            "journal_rows_are_objects": (
                isinstance(plan.get("journal_actions"), list)
                and all(isinstance(row, dict) for row in plan["journal_actions"])
            ),
        },
        "identity": {
            "schema_version": plan.get("schema_version") == 1,
            "recovery_id": plan.get("recovery_id") == context["policy"]["recovery_id"],
            "incident_id": plan.get("incident_id") == context["policy"]["incident_id"],
            "source_checkpoint": plan.get("source_checkpoint")
            == context["source_checkpoint"],
            "external_boundary": plan.get("external_actions_executed") is False,
        },
        "accounts": {
            "complete_object_set": (
                len(raw_decisions) == len(decisions) and set(decisions) == set(scoped)
            ),
            "objects": {
                account_id: account_candidate_checks(
                    decisions.get(account_id, {}), scoped[account_id], context
                )
                for account_id in sorted(scoped)
            },
        },
        "journals": {
            "complete_object_set": (
                len(raw_journal) == len(journal) and set(journal) == set(source_journal)
            ),
            "objects": {
                journal_id: journal_candidate_checks(
                    journal.get(journal_id, {}), source_journal[journal_id]
                )
                for journal_id in sorted(source_journal)
            },
        },
    }
    return all_checks_pass(checks), checks


def load_plan(path: str) -> dict[str, Any]:
    return normalized_plan(read_json(candidate_path(path)))


def state_projection(connection: sqlite3.Connection) -> dict[str, Any]:
    snapshot = database_snapshot(connection)
    return state_projection_from_snapshot(snapshot)


def state_projection_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "accounts": snapshot["accounts"], "markers": snapshot["markers"],
        "queue": snapshot["queue"], "receipts": snapshot["receipts"],
    }


def restore_journal(
    connection: sqlite3.Connection, context: dict[str, Any], plan: dict[str, Any]
) -> None:
    source = {row["journal_id"]: row for row in context["snapshot"]["journal"]}
    for action in plan["journal_actions"]:
        row = source[action["journal_id"]]
        before = json.loads(row["before_json"]) if row["before_json"] else None
        if row["table_name"] == "accounts":
            if before is None:
                connection.execute(
                    "DELETE FROM accounts WHERE account_id=?", (row["record_id"],)
                )
            else:
                connection.execute(
                    """UPDATE accounts SET owner=?,environment=?,compromised=?,
                       durable_version=?,status=?,rotation_marker=?,updated_at=?
                       WHERE account_id=?""",
                    (
                        before["owner"], before["environment"], before["compromised"],
                        before["durable_version"], before["status"],
                        before["rotation_marker"], before["updated_at"],
                        before["account_id"],
                    ),
                )
        elif row["table_name"] == "rotation_queue":
            if before is None:
                connection.execute(
                    "DELETE FROM rotation_queue WHERE queue_id=?", (row["record_id"],)
                )
            else:
                connection.execute(
                    """INSERT OR REPLACE INTO rotation_queue
                       (queue_id,account_id,target_version,status,
                        requested_by_recovery,executed) VALUES (?,?,?,?,?,?)""",
                    tuple(
                        before[key]
                        for key in (
                            "queue_id", "account_id", "target_version", "status",
                            "requested_by_recovery", "executed",
                        )
                    ),
                )
        connection.execute(
            "UPDATE recovery_journal SET restored=1 WHERE journal_id=?",
            (row["journal_id"],),
        )
    prior_ids = sorted({row["recovery_id"] for row in source.values()})
    connection.executemany(
        "UPDATE recovery_runs SET status='rolled_back' "
        "WHERE recovery_id=? AND status='interrupted'",
        [(value,) for value in prior_ids],
    )


def database_candidate_checks(
    plan: dict[str, Any], context: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    pending = {
        row["account_id"]: row
        for row in plan["account_decisions"]
        if row["classification"] == "pending_rotation"
    }
    queue = {row["queue_id"]: row for row in snapshot["queue"]}
    baseline_queue = {row["queue_id"]: row for row in context["base"]["queue"]}
    recovery_queue = {
        row["account_id"]: row
        for row in snapshot["queue"]
        if row["requested_by_recovery"] == plan["recovery_id"]
    }
    receipts = {
        row["account_id"]: row
        for row in snapshot["receipts"]
        if row["recovery_id"] == plan["recovery_id"]
    }
    runs = {row["recovery_id"]: row for row in snapshot["runs"]}
    run = runs.get(plan["recovery_id"], {})
    state_digest = digest(canonical(state_projection_from_snapshot(snapshot)))
    return {
        "restored_accounts": snapshot["accounts"] == context["base"]["accounts"],
        "preserved_markers": snapshot["markers"] == context["base"]["markers"],
        "preserved_system": snapshot["system"] == context["base"]["system"],
        "journal_restored": all(row["restored"] == 1 for row in snapshot["journal"]),
        "prior_runs_rolled_back": all(
            row["status"] == "rolled_back"
            for row in snapshot["runs"]
            if row["recovery_id"] != plan["recovery_id"]
        ),
        "baseline_queue_preserved": all(
            queue.get(key) == value for key, value in baseline_queue.items()
        ),
        "queue_object_set": set(recovery_queue) == set(pending),
        "queue_objects": {
            account_id: (
                recovery_queue.get(account_id, {}).get("queue_id")
                == f"Q-{plan['recovery_id']}-{account_id}"
                and recovery_queue.get(account_id, {}).get("target_version")
                == decision["target_version"]
                and recovery_queue.get(account_id, {}).get("status") == "staged_local"
                and recovery_queue.get(account_id, {}).get("executed") == 0
            )
            for account_id, decision in sorted(pending.items())
        },
        "receipt_object_set": set(receipts)
        == {row["account_id"] for row in plan["account_decisions"]},
        "receipt_objects": {
            row["account_id"]: receipts.get(row["account_id"], {})
            == {
                "recovery_id": plan["recovery_id"],
                "account_id": row["account_id"],
                "classification": row["classification"],
                "action": row["action"],
                "current_version": row["current_version"],
                "target_version": row["target_version"],
            }
            for row in plan["account_decisions"]
        },
        "committed_run": (
            run.get("source_checkpoint") == plan["source_checkpoint"]
            and run.get("semantic_plan_digest") == digest(canonical(plan))
            and run.get("semantic_state_digest") == state_digest
            and run.get("status") == "committed"
        ),
    }


def inspect_command() -> int:
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        context = source_context(connection)
    print(
        json.dumps(
            {
                "incident_id": context["policy"]["incident_id"],
                "recovery_id": context["policy"]["recovery_id"],
                "source_revision": int(context["base"]["system"]["source_revision"]),
                "source_checkpoint": context["source_checkpoint"],
                "source_bundle_valid": context["sources_valid"],
                "scoped_accounts": [
                    row["account_id"] for row in context["scope"]["accounts"]
                ],
                "checkpoint_accounts": [
                    row["account_id"] for row in context["checkpoint"]["accounts"]
                ],
                "interrupted_journals": [
                    {
                        "journal_id": row["journal_id"],
                        "table_name": row["table_name"],
                        "record_id": row["record_id"],
                        "has_before_image": row["before_json"] is not None,
                    }
                    for row in context["snapshot"]["journal"]
                ],
                "commands": ["query", "preview", "apply", "stage", "verify", "replay"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def query_command(sql: str) -> int:
    safe_regular(DB)
    stripped = sql.strip().rstrip(";")
    allowed = {
        "accounts", "durable_markers", "rotation_queue", "decision_receipts",
        "recovery_runs", "recovery_journal", "system_state",
    }
    lowered = stripped.casefold()
    if not lowered.startswith("select ") or any(
        token in lowered
        for token in (" insert ", " update ", " delete ", " pragma ", " attach ")
    ):
        raise ValueError("query accepts one read-only SELECT")
    if not any(f" {table}" in lowered for table in allowed):
        raise ValueError("query must target a published table")
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        cursor = connection.execute(stripped)
        names = [item[0] for item in cursor.description or []]
        print(json.dumps(
            [dict(zip(names, row, strict=True)) for row in cursor.fetchall()],
            indent=2, sort_keys=True,
        ))
    return 0


def preview_command(path: str) -> int:
    try:
        plan = load_plan(path)
        safe_regular(DB)
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
            context = source_context(connection)
        valid, checks = validate_candidate(plan, context)
        diagnostics = {
            "valid": valid and context["sources_valid"],
            "source_bundle_valid": context["sources_valid"],
            "checks": checks,
        }
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as error:
        diagnostics = {
            "valid": False,
            "source_bundle_valid": False,
            "checks": {},
            "error_category": type(error).__name__,
        }
    write_json(".credential_preview.json", diagnostics)
    print(json.dumps(diagnostics, indent=2, sort_keys=True))
    return 0 if diagnostics.get("valid") else 2


def apply_command(path: str) -> int:
    plan = load_plan(path)
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        context = source_context(connection)
    semantic = digest(canonical(plan))
    prior = next(
        (
            row for row in context["snapshot"]["runs"]
            if row["recovery_id"] == plan.get("recovery_id")
            and row["status"] == "committed"
        ),
        None,
    )
    if prior:
        if prior["semantic_plan_digest"] == semantic:
            print('{"status":"idempotent_noop","mutation_count":0}')
            return 0
        print('{"status":"rejected","reason":"recovery identity conflict"}')
        return 4
    valid, checks = validate_candidate(plan, context)
    if not context["sources_valid"] or not valid:
        print(json.dumps(
            {"status": "rejected", "reason": "source or candidate validation failed",
             "checks": checks},
            indent=2, sort_keys=True,
        ))
        return 2
    with sqlite3.connect(DB) as connection:
        connection.execute("BEGIN IMMEDIATE")
        revision = connection.execute(
            "SELECT value FROM system_state WHERE key='source_revision'"
        ).fetchone()
        if not revision or int(revision[0]) != int(context["base"]["system"]["source_revision"]):
            connection.rollback()
            print('{"status":"rejected","reason":"stale source revision"}')
            return 3
        existing = connection.execute(
            "SELECT semantic_plan_digest,status FROM recovery_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
        if existing and existing[1] == "committed":
            connection.rollback()
            if existing[0] == semantic:
                print('{"status":"idempotent_noop","mutation_count":0}')
                return 0
            print('{"status":"rejected","reason":"recovery identity conflict"}')
            return 4
        restore_journal(connection, context, plan)
        for row in plan["account_decisions"]:
            if row["classification"] != "pending_rotation":
                continue
            connection.execute(
                """INSERT INTO rotation_queue
                   (queue_id,account_id,target_version,status,
                    requested_by_recovery,executed) VALUES (?,?,?,?,?,0)""",
                (
                    f"Q-{plan['recovery_id']}-{row['account_id']}",
                    row["account_id"], row["target_version"], "staged_local",
                    plan["recovery_id"],
                ),
            )
        connection.executemany(
            """INSERT INTO decision_receipts
               (recovery_id,account_id,classification,action,
                current_version,target_version) VALUES (?,?,?,?,?,?)""",
            [
                (
                    plan["recovery_id"], row["account_id"], row["classification"],
                    row["action"], row["current_version"], row["target_version"],
                )
                for row in plan["account_decisions"]
            ],
        )
        state_digest = digest(canonical(state_projection(connection)))
        connection.execute(
            """INSERT OR REPLACE INTO recovery_runs
               (recovery_id,source_checkpoint,semantic_plan_digest,
                semantic_state_digest,status) VALUES (?,?,?,?,?)""",
            (
                plan["recovery_id"], plan["source_checkpoint"], semantic,
                state_digest, "committed",
            ),
        )
        connection.commit()
    print(json.dumps(
        {"status": "committed", "semantic_plan_digest": semantic,
         "semantic_state_digest": state_digest, "external_actions_executed": False},
        sort_keys=True,
    ))
    return 0


def stage_payload(
    plan: dict[str, Any], state_digest: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    pending = [
        row for row in plan["account_decisions"]
        if row["classification"] == "pending_rotation"
    ]
    bundle = {
        "schema_version": 1,
        "incident_id": plan["incident_id"],
        "recovery_id": plan["recovery_id"],
        "requests": [
            {"account_id": row["account_id"], "target_version": row["target_version"],
             "status": "queued_local", "executed": False}
            for row in pending
        ],
        "completed_accounts": [
            row["account_id"] for row in plan["account_decisions"]
            if row["classification"] == "completed_durable"
        ],
        "preserved_accounts": [
            row["account_id"] for row in plan["account_decisions"]
            if row["classification"] == "preserved_clean"
        ],
        "credentials_changed": False,
        "revocations_executed": False,
        "external_actions_executed": False,
    }
    manifest = {
        "bundle_sha256": digest(canonical(bundle)),
        "semantic_plan_digest": digest(canonical(plan)),
        "semantic_state_digest": state_digest,
        "source_checkpoint": plan["source_checkpoint"],
    }
    receipt = {
        "manifest_sha256": digest(canonical(manifest)),
        "queue_count": len(pending),
        "status": "local_staged",
        "external_action": False,
    }
    return bundle, manifest, receipt


def stage_command(path: str) -> int:
    plan = load_plan(path)
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        run = connection.execute(
            """SELECT semantic_plan_digest,semantic_state_digest,status
               FROM recovery_runs WHERE recovery_id=?""",
            (plan["recovery_id"],),
        ).fetchone()
    if not run or run[2] != "committed" or run[0] != digest(canonical(plan)):
        print('{"status":"rejected","reason":"plan is not committed"}')
        return 2
    bundle, manifest, receipt = stage_payload(plan, run[1])
    write_json("staging/rotation_queue.json", bundle)
    write_json("staging/queue_manifest.json", manifest)
    write_json("state/recovery_receipt.json", receipt)
    print(json.dumps({"status": "local_staged", "queue_count": len(bundle["requests"])}))
    return 0


def verify_candidate(plan: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        context = source_context(connection)
        snapshot = database_snapshot(connection)
    checks: dict[str, Any] = {
        "source_bundle": context["sources_valid"],
        "candidate": validate_candidate(plan, context)[1],
        "database": database_candidate_checks(plan, context, snapshot),
    }
    state_digest = digest(canonical(state_projection_from_snapshot(snapshot)))
    try:
        bundle = read_json(output_path("staging/rotation_queue.json"))
        manifest = read_json(output_path("staging/queue_manifest.json"))
        receipt = read_json(output_path("state/recovery_receipt.json"))
        staged = stage_payload(plan, state_digest)
        checks["staging"] = {
            "bundle": bundle == staged[0],
            "manifest": manifest == staged[1],
            "receipt": receipt == staged[2],
        }
    except (OSError, ValueError, json.JSONDecodeError) as error:
        checks["staging"] = {"regular_parseable_artifacts": False}
        checks["staging_error"] = {type(error).__name__: False}
    return all_checks_pass(checks), checks, state_digest


def verify_command(path: str) -> int:
    plan = load_plan(path)
    ok, checks, state_digest = verify_candidate(plan)
    report = {
        "status": "pass" if ok else "fail",
        "checks": checks,
        "semantic_plan_digest": digest(canonical(plan)),
        "semantic_state_digest": state_digest,
        "external_actions_executed": False,
    }
    write_json("state/verification.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 2


def replay_command(path: str) -> int:
    plan = load_plan(path)
    safe_regular(DB)
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as connection:
        context = source_context(connection)
        run = connection.execute(
            "SELECT semantic_plan_digest,status FROM recovery_runs WHERE recovery_id=?",
            (plan["recovery_id"],),
        ).fetchone()
    valid, _ = validate_candidate(plan, context)
    semantic = digest(canonical(plan))
    ok, _, _ = verify_candidate(plan)
    if (
        not context["sources_valid"] or not valid or not run
        or run != (semantic, "committed") or not ok
    ):
        print(json.dumps(
            {"status": "rejected", "reason": "stale, conflicting, or unverified replay"},
            sort_keys=True,
        ))
        return 2
    report = {
        "status": "idempotent_noop",
        "mutation_count": 0,
        "semantic_plan_digest": semantic,
    }
    write_json("state/replay_report.json", report)
    print(json.dumps(report, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline credential recovery controller")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect")
    query = subparsers.add_parser("query")
    query.add_argument("sql")
    for name in ("preview", "apply", "stage", "verify", "replay"):
        command = subparsers.add_parser(name)
        command.add_argument("plan")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            return inspect_command()
        if args.command == "query":
            return query_command(args.sql)
        return {
            "preview": preview_command,
            "apply": apply_command,
            "stage": stage_command,
            "verify": verify_command,
            "replay": replay_command,
        }[args.command](args.plan)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as error:
        print(json.dumps({"status": "error", "error_category": type(error).__name__}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
