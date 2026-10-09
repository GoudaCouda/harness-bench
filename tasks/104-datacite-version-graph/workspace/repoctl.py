#!/usr/bin/env python3
"""Local transactional controller for the DataCite repository repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SEED = ROOT / "repository_seed.db"
DB = ROOT / "repository.db"
STATE = ROOT / ".repository_stage_state.json"
RECEIPT = ROOT / "repository_stage_receipt.json"
SOURCES = [
    "change.json",
    "citations.json",
    "policy.md",
    "prior_graph_state.json",
    "records.json",
    "relations.json",
    "repository_seed.db",
]
VALIDATION_FIELDS = {
    "new_version",
    "concept",
    "versions",
    "excluded_records",
    "removed_invalid_edges",
    "corrected_direction_edges",
    "duplicate_relation_edges_removed",
    "duplicate_citations_removed",
    "citation_retargets",
    "citation_preserved",
    "old_versions_retained",
    "cycles",
    "self_edges",
    "prior_checkpoint_id",
    "state_changes",
}
ALLOWED_STATUSES = {
    "retained",
    "added",
    "corrected_direction",
    "deduplicated",
    "retargeted",
    "preserved_concept_citation",
}
EXPECTED_RECORDS = {
    "10.data/cohort",
    "10.data/cohort.v1",
    "10.data/cohort.v2",
    "10.data/cohort.v3",
    "10.data/cohort.v4",
    "10.data/cohort.v3-draft",
}
EXPECTED_CITATIONS = {
    ("10.paper/alpha", "Cites", "10.data/cohort.v2"),
    ("10.paper/beta", "Cites", "10.data/cohort.v4"),
    ("10.paper/gamma", "Cites", "10.data/cohort"),
}
EXPECTED_CHANGE_ACTIONS = {
    "add_version",
    "correct_direction",
    "remove_duplicate",
    "remove_self_edge",
    "remove_draft_edge",
    "remove_duplicate_citation",
    "retarget_citation",
}
LOCAL_REF = re.compile(r"^[A-Za-z0-9_.-]+#[A-Za-z0-9_.-]+$")
FORBIDDEN_SQL = re.compile(
    r"\b(?:attach|detach|pragma|vacuum|alter|drop|trigger|view|virtual|begin|commit|rollback)\b|(?:\.\./|file://)|['\"]\s*/",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: sha256(ROOT / name) for name in SOURCES}


def bundle_sha256() -> str:
    raw = json.dumps(source_hashes(), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path.name}: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name} must contain a JSON object")
    return value


def write_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rows(connection: sqlite3.Connection, query: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(query)]


def lint_database(path: Path) -> dict:
    errors: list[str] = []
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        records = rows(connection, "SELECT * FROM records ORDER BY doi")
        edges = rows(connection, "SELECT * FROM edges ORDER BY edge_id")
        changes = rows(connection, "SELECT * FROM change_log ORDER BY change_id")
    except (sqlite3.Error, OSError) as exc:
        return {"status": "fail", "errors": [f"database unreadable: {exc}"], "counts": {}}
    finally:
        if "connection" in locals():
            connection.close()
    if integrity != "ok":
        errors.append("SQLite integrity_check failed")
    concepts = [record["doi"] for record in records if record["kind"] == "concept" and record["state"] == "findable"]
    versions = [record["doi"] for record in records if record["kind"] == "version" and record["state"] == "findable"]
    drafts = {record["doi"] for record in records if record["state"] != "findable"}
    record_dois = {record["doi"] for record in records}
    if record_dois != EXPECTED_RECORDS:
        errors.append("record set does not match the visible concept, retained versions, new v4, and draft")
    v4 = next((record for record in records if record["doi"] == "10.data/cohort.v4"), None)
    if not v4 or v4["state"] != "findable" or v4["publication_date"] != "2026-04-30":
        errors.append("the CH-2026-04 v4 record is missing or has the wrong release state")
    if len(concepts) != 1:
        errors.append("exactly one findable concept record is required")
    keys = [(edge["from_doi"], edge["relation"], edge["to_doi"]) for edge in edges]
    edge_ids = [str(edge["edge_id"] or "").strip() for edge in edges]
    if any(not edge_id for edge_id in edge_ids) or len(edge_ids) != len(set(edge_ids)):
        errors.append("every final edge requires a nonempty unique edge_id")
    if len(keys) != len(set(keys)):
        errors.append("duplicate canonical edges remain")
    if any(source == target for source, _relation, target in keys):
        errors.append("self-edge remains")
    if any(source in drafts or target in drafts for source, _relation, target in keys):
        errors.append("draft DOI appears in the public graph")
    if concepts:
        concept = concepts[0]
        for version in versions:
            if (concept, "HasVersion", version) not in keys:
                errors.append(f"missing concept membership for {version}")
            if (version, "IsVersionOf", concept) not in keys:
                errors.append(f"missing inverse concept membership for {version}")
    def version_number(doi: str) -> int:
        match = re.search(r"\.v(\d+)$", doi)
        return int(match.group(1)) if match else -1
    ordered = sorted(versions, key=version_number)
    expected_relations: set[tuple[str, str, str]] = set()
    for older, newer in zip(ordered, ordered[1:]):
        expected_relations.add((newer, "IsNewVersionOf", older))
        expected_relations.add((older, "IsPreviousVersionOf", newer))
        if (newer, "IsNewVersionOf", older) not in keys:
            errors.append(f"missing forward version link {newer}->{older}")
        if (older, "IsPreviousVersionOf", newer) not in keys:
            errors.append(f"missing reverse version link {older}->{newer}")
    if concepts:
        concept = concepts[0]
        expected_relations.update((concept, "HasVersion", version) for version in versions)
        expected_relations.update((version, "IsVersionOf", concept) for version in versions)
    public_relations = {key for key in keys if key[1] != "Cites"}
    if public_relations != expected_relations:
        errors.append("the public version graph contains a missing or extra relation")
    invalid_statuses = sorted({edge["status"] for edge in edges} - ALLOWED_STATUSES)
    if invalid_statuses:
        errors.append(f"non-final edge statuses remain: {invalid_statuses}")
    citations = [key for key in keys if key[1] == "Cites"]
    if len(citations) != len(set(citations)):
        errors.append("duplicate citation edges remain")
    if set(citations) != EXPECTED_CITATIONS:
        errors.append("citation targets do not follow the dated local citation policy")
    for edge in edges:
        refs = [part.strip() for part in edge["evidence_refs"].split(";") if part.strip()]
        if not refs or not all(LOCAL_REF.fullmatch(ref) for ref in refs):
            errors.append(f"edge {edge['edge_id']} lacks valid local evidence references")
    actions = {change["action"] for change in changes}
    change_ids = [str(change["change_id"] or "").strip() for change in changes]
    if any(not change_id for change_id in change_ids) or len(change_ids) != len(set(change_ids)):
        errors.append("every change_log row requires a nonempty unique change_id")
    if len(changes) != len(EXPECTED_CHANGE_ACTIONS) or actions != EXPECTED_CHANGE_ACTIONS:
        errors.append("change_log must contain one row for each required repair action")
    for change in changes:
        if not LOCAL_REF.fullmatch(change["source_ref"]):
            errors.append(f"change {change['change_id']} has an invalid source_ref")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "counts": {"records": len(records), "edges": len(edges), "changes": len(changes)},
    }


def command_status(_: argparse.Namespace) -> int:
    state = read_json(STATE)
    state["sources_intact"] = state.get("input_bundle_sha256") == bundle_sha256()
    state["repository_sha256_current"] = sha256(DB) if DB.is_file() else None
    state["lint"] = lint_database(DB) if DB.is_file() else {"status": "fail", "errors": ["repository.db missing"]}
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    allowed = {"records", "edges", "change_log"}
    if args.table not in allowed:
        raise SystemExit(f"table must be one of {sorted(allowed)}")
    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        value = rows(connection, f"SELECT * FROM {args.table} ORDER BY 1")
    finally:
        connection.close()
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def command_schema(args: argparse.Namespace) -> int:
    allowed = {"records", "edges", "change_log"}
    if args.table not in allowed:
        raise SystemExit(f"table must be one of {sorted(allowed)}")
    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        columns = [
            {
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "primary_key_position": row["pk"],
            }
            for row in connection.execute(f"PRAGMA table_info({args.table})")
        ]
    finally:
        connection.close()
    print(json.dumps({"table": args.table, "columns": columns}, indent=2, sort_keys=True))
    return 0


def command_reset(_: argparse.Namespace) -> int:
    state = read_json(STATE)
    if state.get("input_bundle_sha256") != bundle_sha256():
        raise SystemExit("immutable source bundle no longer matches controller state")
    shutil.copy2(SEED, DB)
    state.update({"phase": "draft", "revision": int(state.get("revision", 0)) + 1, "migration_sha256": None, "repository_sha256": sha256(DB), "stage_token": None, "external_actions_executed": False})
    write_state(state)
    if RECEIPT.exists():
        RECEIPT.unlink()
    print(json.dumps({"status": "reset", "repository_sha256": sha256(DB)}, indent=2))
    return 0


def command_apply(args: argparse.Namespace) -> int:
    migration = (ROOT / args.file).resolve()
    if migration.parent != ROOT or not migration.is_file():
        raise SystemExit("migration must be a regular file at the workspace root")
    sql = migration.read_text(encoding="utf-8")
    if not sql.strip() or FORBIDDEN_SQL.search(sql):
        raise SystemExit("migration contains an empty, path-bearing, or forbidden SQL operation")
    state = read_json(STATE)
    if state.get("input_bundle_sha256") != bundle_sha256():
        raise SystemExit("immutable source bundle no longer matches controller state")
    with tempfile.NamedTemporaryFile(dir=ROOT, suffix=".db", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        shutil.copy2(SEED, temporary)
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + sql + "\nCOMMIT;")
        except sqlite3.Error:
            connection.rollback()
            raise
        finally:
            connection.close()
        result = lint_database(temporary)
        if result["status"] != "pass":
            print(json.dumps(result, indent=2, sort_keys=True))
            return 2
        temporary.replace(DB)
    except (OSError, UnicodeError, sqlite3.Error) as exc:
        raise SystemExit(f"migration failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    state.update({"phase": "migrated", "revision": int(state.get("revision", 0)) + 1, "migration_sha256": sha256(migration), "repository_sha256": sha256(DB), "stage_token": None, "external_actions_executed": False})
    write_state(state)
    print(json.dumps({"status": "applied", "lint": lint_database(DB)}, indent=2, sort_keys=True))
    return 0


def validate_package() -> dict:
    errors = list(lint_database(DB).get("errors", []))
    migration = ROOT / "migration.sql"
    if not migration.is_file() or not migration.read_text(encoding="utf-8").strip():
        errors.append("migration.sql is missing or empty")
    try:
        validation = read_json(ROOT / "graph_validation.json")
        if set(validation) != VALIDATION_FIELDS:
            errors.append("graph_validation.json must use the exact published top-level fields")
    except SystemExit as exc:
        errors.append(str(exc))
    decision = ROOT / "version_decision.md"
    if not decision.is_file() or decision.stat().st_size < 500:
        errors.append("version_decision.md is missing or too small for a handoff")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def command_validate(_: argparse.Namespace) -> int:
    result = validate_package()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def stage_token(bundle: str, repository: str, migration: str, validation: str, decision: str) -> str:
    raw = f"datacite-v4-repair\n{bundle}\n{repository}\n{migration}\n{validation}\n{decision}\nlocal-only\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def receipt_for(state: dict) -> dict:
    return {
        "receipt_type": "local_repository_stage",
        "checkpoint_id": "datacite-v4-repair",
        "state_revision": state["revision"],
        "phase": "staged_for_metadata_review",
        "input_bundle_sha256": state["input_bundle_sha256"],
        "repository_sha256": state["repository_sha256"],
        "migration_sha256": state["migration_sha256"],
        "validation_sha256": state["validation_sha256"],
        "decision_sha256": state["decision_sha256"],
        "stage_token": state["stage_token"],
        "external_actions_executed": False,
    }


def command_stage(_: argparse.Namespace) -> int:
    result = validate_package()
    if result["status"] != "pass":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    state = read_json(STATE)
    bundle = bundle_sha256()
    repository = sha256(DB)
    migration = sha256(ROOT / "migration.sql")
    validation = sha256(ROOT / "graph_validation.json")
    decision = sha256(ROOT / "version_decision.md")
    token = stage_token(bundle, repository, migration, validation, decision)
    same = state.get("phase") == "staged_for_metadata_review" and state.get("stage_token") == token
    if not same:
        state.update({"phase": "staged_for_metadata_review", "revision": int(state.get("revision", 0)) + 1, "input_bundle_sha256": bundle, "repository_sha256": repository, "migration_sha256": migration, "validation_sha256": validation, "decision_sha256": decision, "stage_token": token, "external_actions_executed": False})
        write_state(state)
        RECEIPT.write_text(json.dumps(receipt_for(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "staged", "idempotent_replay": same, "stage_token": token}, indent=2, sort_keys=True))
    return 0


def command_replay(_: argparse.Namespace) -> int:
    state = read_json(STATE)
    errors: list[str] = []
    if state.get("phase") != "staged_for_metadata_review" or not RECEIPT.is_file():
        errors.append("package has not been staged")
    else:
        bundle = bundle_sha256()
        repository = sha256(DB)
        migration = sha256(ROOT / "migration.sql")
        validation = sha256(ROOT / "graph_validation.json")
        decision = sha256(ROOT / "version_decision.md")
        token = stage_token(bundle, repository, migration, validation, decision)
        if (bundle, repository, migration, validation, decision, token) != (state.get("input_bundle_sha256"), state.get("repository_sha256"), state.get("migration_sha256"), state.get("validation_sha256"), state.get("decision_sha256"), state.get("stage_token")):
            errors.append("staged package hashes are stale")
        if read_json(RECEIPT) != receipt_for(state):
            errors.append("stage receipt mismatch")
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "stage_token": state.get("stage_token")}, indent=2, sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Local DataCite repository migration controller")
    sub = parser.add_subparsers(required=True)
    for name, func in (("status", command_status), ("reset", command_reset), ("validate", command_validate), ("stage", command_stage), ("replay", command_replay)):
        item = sub.add_parser(name)
        item.set_defaults(func=func)
    for name, func in (("inspect", command_inspect), ("schema", command_schema)):
        item = sub.add_parser(name)
        item.add_argument("--table", required=True)
        item.set_defaults(func=func)
    apply = sub.add_parser("apply")
    apply.add_argument("--file", default="migration.sql")
    apply.set_defaults(func=command_apply)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
