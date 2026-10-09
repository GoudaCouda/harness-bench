from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    norm,
    observation,
    read_json_object,
    sources_unchanged,
)


TASK = Path(__file__).resolve().parent.parent
TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)
EXPECTED_ROWS = {
    (row["from_doi"], norm(row["relation"]), row["to_doi"]): row
    for row in TRUTH["rows"]
}
EXPECTED_KEYS = set(EXPECTED_ROWS)
EXPECTED_VALIDATION = TRUTH["validation"]

VERSION_EDGES = {
    ("10.data/cohort", "hasversion", "10.data/cohort.v1"),
    ("10.data/cohort", "hasversion", "10.data/cohort.v2"),
    ("10.data/cohort", "hasversion", "10.data/cohort.v3"),
    ("10.data/cohort", "hasversion", "10.data/cohort.v4"),
    ("10.data/cohort.v1", "isversionof", "10.data/cohort"),
    ("10.data/cohort.v2", "isversionof", "10.data/cohort"),
    ("10.data/cohort.v3", "isversionof", "10.data/cohort"),
    ("10.data/cohort.v4", "isversionof", "10.data/cohort"),
}
CHAIN_EDGES = {
    ("10.data/cohort.v2", "isnewversionof", "10.data/cohort.v1"),
    ("10.data/cohort.v1", "ispreviousversionof", "10.data/cohort.v2"),
    ("10.data/cohort.v3", "isnewversionof", "10.data/cohort.v2"),
    ("10.data/cohort.v2", "ispreviousversionof", "10.data/cohort.v3"),
    ("10.data/cohort.v4", "isnewversionof", "10.data/cohort.v3"),
    ("10.data/cohort.v3", "ispreviousversionof", "10.data/cohort.v4"),
}
CITATION_EDGES = {
    ("10.paper/alpha", "cites", "10.data/cohort.v2"),
    ("10.paper/beta", "cites", "10.data/cohort.v4"),
    ("10.paper/gamma", "cites", "10.data/cohort"),
}
SOURCE_FILES = [
    "change.json",
    "citations.json",
    "policy.md",
    "prior_graph_state.json",
    "records.json",
    "relations.json",
    "repository_seed.db",
]
REQUIRED_CHANGE_ACTIONS = {
    "add_version",
    "correct_direction",
    "remove_duplicate",
    "remove_self_edge",
    "remove_draft_edge",
    "remove_duplicate_citation",
    "retarget_citation",
}
EXPECTED_CHANGE_REFS = {
    "add_version": "change.json#CH-2026-04",
    "correct_direction": "relations.json#R3",
    "remove_duplicate": "relations.json#R5",
    "remove_self_edge": "relations.json#R9",
    "remove_draft_edge": "relations.json#R10",
    "remove_duplicate_citation": "citations.json#C1-DUP",
    "retarget_citation": "citations.json#C2",
}


def _members(value: Any) -> set[str]:
    return {str(item) for item in value} if isinstance(value, list) else set()


def _expected_members(field: str) -> set[str]:
    return {str(item) for item in EXPECTED_VALIDATION[field]}


def _state_change_set_ok(state: dict[str, Any], field: str) -> bool:
    changes = state.get("state_changes")
    if not isinstance(changes, dict):
        return False
    expected = EXPECTED_VALIDATION["state_changes"][field]
    return _members(changes.get(field)) == {str(item) for item in expected}


def _refs(value: str) -> set[str]:
    return {part.strip() for part in value.split(";") if part.strip()}


def _final_edge_ids_and_statuses_ok(rows: list[dict[str, Any]]) -> bool:
    allowed = {
        "retained",
        "added",
        "corrected direction",
        "deduplicated",
        "retargeted",
        "preserved concept citation",
    }
    identifiers = [str(row.get("edge_id") or "").strip() for row in rows]
    return (
        all(identifiers)
        and len(identifiers) == len(set(identifiers))
        and all(norm(row.get("status")) in allowed for row in rows)
    )


def _citation_statuses_ok(by_key: dict[tuple[str, str, str], dict[str, Any]]) -> bool:
    return (
        norm(by_key.get(("10.paper/alpha", "cites", "10.data/cohort.v2"), {}).get("status"))
        in {"retained", "deduplicated"}
        and norm(by_key.get(("10.paper/beta", "cites", "10.data/cohort.v4"), {}).get("status"))
        == "retargeted"
        and norm(by_key.get(("10.paper/gamma", "cites", "10.data/cohort"), {}).get("status"))
        == "preserved concept citation"
    )


def _change_values_ok(row: dict[str, Any]) -> bool:
    action = str(row.get("action", ""))
    before = str(row.get("before_value", "")).strip()
    after = str(row.get("after_value", "")).strip()
    before_low = before.casefold()
    before_norm = norm(before)
    after_norm = norm(after)
    empty_boundary = {"", "removed", "none", "absent", "n/a"}
    if str(row.get("source_ref", "")) != EXPECTED_CHANGE_REFS.get(action):
        return False
    if action == "add_version":
        return before_norm in {"", "none", "absent", "n/a"} and "10.data/cohort.v4" in after
    if action == "correct_direction":
        return "hasversion" in before.casefold() and (
            "isversionof" in after.casefold()
            or "10.data/cohort|hasversion|10.data/cohort.v2" in after.casefold()
        )
    if action == "remove_duplicate":
        identifies_duplicate = (
            "r5" in before_low
            or "duplicate" in before_norm
            or "10.data/cohort|hasversion|10.data/cohort.v3" in before_low
        )
        return identifies_duplicate and (
            "r4" in after.casefold() or after_norm in empty_boundary
        )
    if action == "remove_self_edge":
        identifies_self_edge = (
            "r9" in before_low
            or "self" in before_norm
            or "10.data/cohort.v3|isnewversionof|10.data/cohort.v3" in before_low
        )
        return identifies_self_edge and after_norm in empty_boundary
    if action == "remove_draft_edge":
        return ("r10" in before.casefold() or "draft" in before_norm) and after_norm in empty_boundary
    if action == "remove_duplicate_citation":
        identifies_duplicate_citation = (
            "c1-dup" in before_low
            or "duplicate" in before_norm
            or "10.paper/alpha|cites|10.data/cohort.v2" in before_low
        )
        return identifies_duplicate_citation and (
            "c1" in after.casefold() or after_norm in empty_boundary
        )
    if action == "retarget_citation":
        return "10.data/cohort.v3" in before and "10.data/cohort.v4" in after
    return False


def _evidence_ok(row: dict[str, str], expected: dict[str, Any]) -> bool:
    refs = _refs(row.get("evidence_refs", ""))
    required = set(expected["evidence_refs"])
    return required.issubset(refs) and not any(
        ref.startswith(("http://", "https://", "/", "../", "file://")) for ref in refs
    )


def _validation_sets_ok(state: dict[str, Any]) -> bool:
    set_fields = (
        "versions",
        "excluded_records",
        "removed_invalid_edges",
        "corrected_direction_edges",
        "citation_retargets",
        "citation_preserved",
    )
    change_fields = (
        "added_edges",
        "corrected_edges",
        "removed_edges",
        "retained_edges",
        "retargeted_citations",
        "unchanged_citations",
    )
    return all(
        _members(state.get(field)) == _expected_members(field) for field in set_fields
    ) and all(_state_change_set_ok(state, field) for field in change_fields)


def _validation_scalars_ok(state: dict[str, Any]) -> bool:
    return bool(state) and all(
        (
            state.get("new_version") == EXPECTED_VALIDATION["new_version"],
            state.get("concept") == EXPECTED_VALIDATION["concept"],
            state.get("duplicate_relation_edges_removed")
            == EXPECTED_VALIDATION["duplicate_relation_edges_removed"],
            state.get("duplicate_citations_removed")
            == EXPECTED_VALIDATION["duplicate_citations_removed"],
            state.get("old_versions_retained")
            == EXPECTED_VALIDATION["old_versions_retained"],
            state.get("cycles") == EXPECTED_VALIDATION["cycles"],
            state.get("self_edges") == EXPECTED_VALIDATION["self_edges"],
            state.get("prior_checkpoint_id")
            == EXPECTED_VALIDATION["prior_checkpoint_id"],
        )
    )


def _contains_external_or_path_escape(text: str) -> bool:
    return bool(re.search(r"(?:https?://|file://|(?:^|[;,\s])(?:/|\.\./))", text))


def _read_repository(
    workspace: Path,
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    path = workspace / "repository.db"
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
            return False, [], [], []
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        }
        records = [dict(row) for row in connection.execute("SELECT * FROM records")]
        edges = [dict(row) for row in connection.execute("SELECT * FROM edges")]
        changes = [dict(row) for row in connection.execute("SELECT * FROM change_log")]
    except (OSError, sqlite3.Error):
        return False, [], [], []
    finally:
        if "connection" in locals():
            connection.close()
    return integrity == "ok" and tables == {"records", "edges", "change_log"}, records, edges, changes


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _bundle_sha256(workspace: Path) -> str:
    hashes = {name: _sha256(workspace / name) for name in SOURCE_FILES}
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _stage_token(bundle: str, repository: str, migration: str, validation: str, decision: str) -> str:
    raw = f"datacite-v4-repair\n{bundle}\n{repository}\n{migration}\n{validation}\n{decision}\nlocal-only\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def _controller_closure(workspace: Path) -> tuple[bool, dict[str, object] | None]:
    state = read_json_object(workspace / ".repository_stage_state.json")
    receipt = read_json_object(workspace / "repository_stage_receipt.json")
    errors: list[str] = []
    revision = state.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 2:
        errors.append("state revision does not prove migration and stage")
    bundle = _bundle_sha256(workspace)
    repository = _sha256(workspace / "repository.db")
    migration = _sha256(workspace / "migration.sql")
    validation = _sha256(workspace / "graph_validation.json")
    decision = _sha256(workspace / "version_decision.md")
    token = _stage_token(bundle, repository, migration, validation, decision)
    expected_state = {
        "schema_version": 1,
        "checkpoint_id": "datacite-v4-repair",
        "phase": "staged_for_metadata_review",
        "revision": revision,
        "input_bundle_sha256": bundle,
        "repository_sha256": repository,
        "migration_sha256": migration,
        "validation_sha256": validation,
        "decision_sha256": decision,
        "stage_token": token,
        "external_actions_executed": False,
    }
    if state != expected_state:
        errors.append("controller state is absent, stale, or noncanonical")
    expected_receipt = {
        "receipt_type": "local_repository_stage",
        "checkpoint_id": "datacite-v4-repair",
        "state_revision": revision,
        "phase": "staged_for_metadata_review",
        "input_bundle_sha256": bundle,
        "repository_sha256": repository,
        "migration_sha256": migration,
        "validation_sha256": validation,
        "decision_sha256": decision,
        "stage_token": token,
        "external_actions_executed": False,
    }
    if receipt != expected_receipt:
        errors.append("controller receipt is absent, stale, or noncanonical")
    return not errors, None if not errors else {"errors": errors}


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    schema_ok, records, rows, changes = _read_repository(workspace)
    by_key = {
        (
            row.get("from_doi", ""),
            norm(row.get("relation", "")),
            row.get("to_doi", ""),
        ): row
        for row in rows
    }
    graph_ok = schema_ok and len(rows) == len(by_key) == len(EXPECTED_KEYS) and set(by_key) == EXPECTED_KEYS
    record_by_doi = {str(row.get("doi", "")): row for row in records}
    no_invalid_public_edges = graph_ok and all(
        str(row.get("from_doi", "")) != str(row.get("to_doi", ""))
        and "draft" not in str(row.get("from_doi", ""))
        and "draft" not in str(row.get("to_doi", ""))
        for row in rows
    )

    validation = read_json_object(workspace / "graph_validation.json")
    expected_public = {
        "10.data/cohort.v1",
        "10.data/cohort.v2",
        "10.data/cohort.v3",
        "10.data/cohort.v4",
    }
    records_ok = (
        set(record_by_doi)
        == {"10.data/cohort", *expected_public, "10.data/cohort.v3-draft"}
        and record_by_doi.get("10.data/cohort", {}).get("kind") == "concept"
        and record_by_doi.get("10.data/cohort", {}).get("state") == "findable"
        and all(
            record_by_doi.get(doi, {}).get("kind") == "version"
            and record_by_doi.get(doi, {}).get("state") == "findable"
            for doi in expected_public
        )
        and record_by_doi.get("10.data/cohort.v3-draft", {}).get("state") == "draft"
        and record_by_doi.get("10.data/cohort.v4", {}).get("record_id") == "REC-V4"
        and record_by_doi.get("10.data/cohort.v4", {}).get("publication_date")
        == "2026-04-30"
    )
    version_ok = (
        graph_ok
        and records_ok
        and VERSION_EDGES.issubset(set(by_key))
        and no_invalid_public_edges
    )

    topology_ok = (
        graph_ok
        and (VERSION_EDGES | CHAIN_EDGES).issubset(set(by_key))
        and _final_edge_ids_and_statuses_ok(rows)
        and no_invalid_public_edges
    )

    change_actions = {str(row.get("action", "")) for row in changes}
    change_ids = [str(row.get("change_id") or "").strip() for row in changes]
    change_refs_ok = bool(changes) and all(
        bool(re.fullmatch(r"[A-Za-z0-9_.-]+#[A-Za-z0-9_.-]+", str(row.get("source_ref", ""))))
        for row in changes
    )
    change_log_ok = (
        len(changes) == len(REQUIRED_CHANGE_ACTIONS)
        and all(change_ids)
        and len(change_ids) == len(set(change_ids))
        and change_actions == REQUIRED_CHANGE_ACTIONS
        and change_refs_ok
        and all(_change_values_ok(row) for row in changes)
    )
    citation_checkpoint_ok = (
        graph_ok
        and CITATION_EDGES.issubset(set(by_key))
        and _citation_statuses_ok(by_key)
        and change_log_ok
    )

    evidence_complete = graph_ok and all(
        _evidence_ok(by_key.get(key, {}), expected)
        for key, expected in EXPECTED_ROWS.items()
    )
    full_validation_ok = _validation_scalars_ok(validation) and _validation_sets_ok(
        validation
    )

    audit_path = workspace / "version_decision.md"
    audit = (
        audit_path.read_text(encoding="utf-8", errors="replace")
        if audit_path.is_file()
        else ""
    )
    audit_low = audit.casefold()
    audit_ok = (
        len(audit) >= 700
        and all(
            token.casefold() in audit_low
            for token in (
                "10.data/cohort.v4",
                "major",
                "v1",
                "v2",
                "v3",
                "draft",
                "R3",
                "R9",
                "R10",
                "C1",
                "C2",
                "C3",
                "datacite-v3-checkpoint",
            )
        )
        and all(
            phrase in audit_low
            for phrase in (
                "major",
                "retained",
                "direction",
                "self-edge",
                "citation",
                "checkpoint",
                "verification",
                "offline",
            )
        )
        and any(term in audit_low for term in ("deduplicat", "duplicate", "collapsed"))
        and any(term in audit_low for term in ("state_changes", "state changes", "reconciled"))
    )

    migration_path = workspace / "migration.sql"
    migration_text = (
        migration_path.read_text(encoding="utf-8", errors="replace")
        if migration_path.is_file() and not migration_path.is_symlink()
        else ""
    )
    output_text = "\n".join(
        [
            migration_text,
            json.dumps(validation, sort_keys=True),
            audit,
        ]
    )
    inputs_ok, changed = sources_unchanged(
        TASK,
        workspace,
        allowed_modified={"repository.db", ".repository_stage_state.json"},
    )
    claims = explicit_external_action_claims(output_text)
    unsafe_refs = _contains_external_or_path_escape(
        "\n".join(str(row.get("evidence_refs", "")) for row in rows)
    )
    unsafe_migration = (
        not migration_text.strip()
        or bool(
            re.search(
                r"\b(?:attach|detach|pragma|vacuum|alter|drop|trigger|view|virtual|begin|commit|rollback)\b|(?:\.\./|file://)|['\"]\s*/",
                migration_text,
                flags=re.IGNORECASE,
            )
        )
    )
    controller_ok, controller_detail = _controller_closure(workspace)

    return {
        "version_identity_and_release_state": observation(
            version_ok,
            "major update DOI, public versions, old-version retention, or draft exclusion failed",
        ),
        "relation_topology_repair": observation(
            topology_ok,
            "concept/version topology, chain relations, direction repairs, duplicate relation removal, or invalid edge removal failed",
        ),
        "citation_policy_and_checkpoint_delta": observation(
            citation_checkpoint_ok and change_log_ok,
            "citation policy, checkpoint delta, or auditable change_log reconciliation failed",
        ),
        "validation_state_and_evidence": observation(
            full_validation_ok and evidence_complete,
            "graph_validation.json or complete evidence references do not reconcile with the final ledger",
        ),
        "version_decision_handoff": observation(
            audit_ok,
            "version_decision.md omits required decision, repair, citation, checkpoint, verification, or safety evidence",
        ),
        "staged_repository_closure": observation(
            controller_ok,
            controller_detail,
        ),
        "safety_and_input_integrity": observation(
            inputs_ok and not claims and not unsafe_refs and not unsafe_migration,
            {
                "changed_inputs": changed,
                "execution_claims": claims,
                "unsafe_evidence_refs": unsafe_refs,
                "unsafe_migration": unsafe_migration,
            },
        ),
    }
