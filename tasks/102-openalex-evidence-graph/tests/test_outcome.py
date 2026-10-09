from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any

from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    norm,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
    substantive_prose,
)
from harnessbench.grading.structured_io import StructuredDataError, read_json_file


TASK = Path(__file__).resolve().parent.parent
TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)
HEADER = list(TRUTH["header"])
EXPECTED_ROWS = {row["work_id"]: row for row in TRUTH["rows"]}
EXPECTED_IDS = set(EXPECTED_ROWS)
EXPECTED_COVERAGE = TRUTH["coverage"]

PAGINATION_CASE = {
    "W1",
    "W2",
    "W3",
    "W1-DUP",
    "W4",
    "W5",
    "W6",
    "W8",
    "W4-ALIAS",
    "W5-CONFLICT",
    "W7",
    "W8-CORR",
    "W9",
    "W10",
}
ENTITY_CASE = {"W1", "W1-DUP", "W4", "W4-ALIAS", "W7", "W9", "W8", "W10"}
CONFLICT_CASE = {
    "W2",
    "W3",
    "W5",
    "W5-CONFLICT",
    "W6",
    "W8",
    "W8-CORR",
    "W7",
    "W10",
}
CONTROLLER_SOURCE_FILES = [
    "authors.json",
    "concepts.json",
    "correction_events.json",
    "pages_index.json",
    "policy.md",
    "prior_graph_state.json",
    "works_page1.json",
    "works_page2.json",
    "works_page4.json",
]


def _members(value: Any) -> set[str]:
    return {str(item) for item in value} if isinstance(value, list) else set()


def _expected_members(field: str) -> set[str]:
    return {str(item) for item in EXPECTED_COVERAGE[field]}


def _split(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[|,]", value) if part.strip()]


def _refs(value: str) -> set[str]:
    return {part.strip() for part in value.split(";") if part.strip()}


def _status_matches(actual: str, expected: str) -> bool:
    aliases = {
        "canonical": {"canonical", "active", "retained"},
        "duplicate": {"duplicate", "duplicate work"},
        "quarantined suspected match": {
            "quarantined suspected match",
            "suspected match",
            "suspected doi",
        },
        "quarantined conflict": {"quarantined conflict", "conflict quarantine"},
        "superseded by correction": {
            "superseded by correction",
            "superseded",
            "corrected superseded",
        },
        "review required": {"review required", "needs review", "dependency review"},
    }
    expected_norm = norm(expected)
    return norm(actual) in aliases.get(expected_norm, {expected_norm})


def _relation_matches(actual: str, expected: str) -> bool:
    return norm(actual) == norm(expected)


def _row_business_ok(
    row: dict[str, str],
    expected: dict[str, Any],
    *,
    require_issue: bool = True,
) -> bool:
    issue_expected = str(expected["issue"])
    issue_ok = True
    if require_issue and issue_expected:
        issue_ok = norm(row.get("issue")) == norm(issue_expected)
    elif require_issue:
        issue_ok = not row.get("issue", "").strip()
    return (
        row.get("canonical_work_id") == expected["canonical_work_id"]
        and row.get("canonical_key", "").casefold() == expected["canonical_key"]
        and _split(row.get("author_ids", "")) == _split(expected["author_ids"])
        and _split(row.get("institution_ids", ""))
        == _split(expected["institution_ids"])
        and _split(row.get("referenced_work_ids", ""))
        == _split(expected["referenced_work_ids"])
        and _split(row.get("concept_ids", "")) == _split(expected["concept_ids"])
        and _relation_matches(row.get("claim_relation", ""), expected["claim_relation"])
        and _status_matches(row.get("status", ""), expected["status"])
        and issue_ok
    )


def _evidence_ok(
    row: dict[str, str], expected: dict[str, Any], *, strict: bool
) -> bool:
    refs = _refs(row.get("evidence_refs", ""))
    required = (
        set(expected["evidence_refs"]) if strict else {expected["evidence_refs"][0]}
    )
    return required.issubset(refs) and not any(
        ref.startswith(("http://", "https://", "/", "../", "file://")) for ref in refs
    )


def _state_set_ok(state: dict[str, Any], field: str) -> bool:
    return _members(state.get(field)) == _expected_members(field)


def _count_or_exact_members_ok(
    state: dict[str, Any], field: str, expected_members: set[str]
) -> bool:
    value = state.get(field)
    if isinstance(value, int) and not isinstance(value, bool):
        return value == len(expected_members)
    return _members(value) == expected_members


def _canonical_work_ids() -> set[str]:
    return {str(row["canonical_work_id"]) for row in EXPECTED_ROWS.values()}


def _author_ids() -> set[str]:
    authors = json.loads(
        (TASK / "workspace" / "authors.json").read_text(encoding="utf-8")
    )
    return {str(author["id"]) for author in authors}


def _retained_relation_work_ids(relation: str) -> set[str]:
    excluded = {
        "duplicate",
        "quarantined_suspected_match",
        "quarantined_conflict",
        "review_required",
        "superseded_by_correction",
    }
    return {
        str(row["work_id"])
        for row in EXPECTED_ROWS.values()
        if str(row["claim_relation"]) == relation
        and str(row["status"]) not in excluded
    }


def _state_change_set_ok(state: dict[str, Any], field: str) -> bool:
    changes = state.get("state_changes")
    if not isinstance(changes, dict):
        return False
    expected = EXPECTED_COVERAGE["state_changes"][field]
    return _members(changes.get(field)) == {str(item) for item in expected}


def _checkpoint_ok(state: dict[str, Any]) -> bool:
    return (
        state.get("prior_checkpoint_id") == EXPECTED_COVERAGE["prior_checkpoint_id"]
        and _members(state.get("prior_processed_pages"))
        == _expected_members("prior_processed_pages")
        and _members(state.get("new_pages_consumed"))
        == _expected_members("new_pages_consumed")
        and all(
            _state_change_set_ok(state, field)
            for field in (
                "released_from_review",
                "added_review_required",
                "newly_quarantined",
                "unchanged_quarantined",
                "new_duplicates",
                "unchanged_duplicates",
                "changed_statuses",
            )
        )
    )


def _state_ok(state: dict[str, Any]) -> bool:
    return bool(state) and all(
        (
            _members(state.get("pages_consumed"))
            == _expected_members("pages_consumed"),
            _members(state.get("pages_declared_not_found"))
            == _expected_members("pages_declared_not_found"),
            state.get("prior_checkpoint_id")
            == EXPECTED_COVERAGE["prior_checkpoint_id"],
            _state_set_ok(state, "prior_processed_pages"),
            _state_set_ok(state, "new_pages_consumed"),
            state.get("observed_work_rows") == EXPECTED_COVERAGE["observed_work_rows"],
            _count_or_exact_members_ok(
                state, "canonical_works", _canonical_work_ids()
            ),
            _count_or_exact_members_ok(state, "authors", _author_ids()),
            _count_or_exact_members_ok(
                state, "supporting_works", _retained_relation_work_ids("supports")
            ),
            _count_or_exact_members_ok(
                state,
                "contradicting_works",
                _retained_relation_work_ids("contradicts"),
            ),
            _state_set_ok(state, "duplicate_works"),
            _state_set_ok(state, "non_duplicate_version_aliases"),
            _state_set_ok(state, "authors_named_alex_kim"),
            _state_set_ok(state, "unknown_affiliations"),
            _state_set_ok(state, "orphan_authors"),
            _state_set_ok(state, "quarantined_works"),
            _state_set_ok(state, "conflicting_canonical_works"),
            _state_set_ok(state, "resolved_correction_works"),
            _state_set_ok(state, "review_required_works"),
            _state_set_ok(state, "review_required_edges"),
            _state_set_ok(state, "dangling_references"),
            _state_set_ok(state, "page_row_count_mismatches"),
            _checkpoint_ok(state),
        )
    )


def _contains_external_or_path_escape(text: str) -> bool:
    return bool(re.search(r"(?:https?://|file://|(?:^|[;,\s])(?:/|\.\./))", text))


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _bundle_sha256(workspace: Path) -> str:
    hashes = {name: _sha256(workspace / name) for name in CONTROLLER_SOURCE_FILES}
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _stage_token(bundle: str, graph: str, coverage: str, audit: str) -> str:
    raw = (
        f"openalex-synthetic-graph-102\n{bundle}\n{graph}\n{coverage}\n"
        f"{audit}\noffline\n"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _controller_closure(workspace: Path) -> tuple[bool, dict[str, object] | None]:
    errors: list[str] = []
    try:
        state = read_json_file(
            workspace / ".graph_repair_state.json", max_bytes=64_000
        )
    except StructuredDataError as exc:
        state = {}
        errors.append(f"state: {exc}")
    try:
        receipt = read_json_file(
            workspace / "graph_stage_receipt.json", max_bytes=64_000
        )
    except StructuredDataError as exc:
        receipt = {}
        errors.append(f"receipt: {exc}")
    if not isinstance(state, dict):
        state = {}
        errors.append("state must be an object")
    if not isinstance(receipt, dict):
        receipt = {}
        errors.append("receipt must be an object")

    revision = state.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 3:
        errors.append("state revision does not prove page-3/page-4 recovery and stage")
    bundle = _bundle_sha256(workspace)
    graph = _sha256(workspace / "evidence_graph.csv")
    coverage = _sha256(workspace / "coverage.json")
    audit = _sha256(workspace / "graph_audit.md")
    token = _stage_token(bundle, graph, coverage, audit)
    observations = {
        "1": {
            "page": 1,
            "file": "works_page1.json",
            "status": "consumed",
            "expected_rows": 3,
            "observed_rows": 3,
            "row_count_mismatch": None,
        },
        "2": {
            "page": 2,
            "file": "works_page2.json",
            "status": "consumed",
            "expected_rows": 5,
            "observed_rows": 5,
            "row_count_mismatch": None,
        },
        "3": {
            "page": 3,
            "file": "works_page3.json",
            "status": "declared_not_found",
            "expected_rows": 2,
            "observed_rows": None,
            "row_count_mismatch": None,
        },
        "4": {
            "page": 4,
            "file": "works_page4.json",
            "status": "consumed",
            "expected_rows": 7,
            "observed_rows": 6,
            "row_count_mismatch": "page:4:expected:7:observed:6",
        },
    }
    expected_state = {
        "schema_version": 1,
        "export_id": "openalex-synthetic-graph-102",
        "phase": "staged_for_handoff",
        "revision": revision,
        "input_bundle_sha256": bundle,
        "page_observations": observations,
        "graph_sha256": graph,
        "coverage_sha256": coverage,
        "audit_sha256": audit,
        "stage_token": token,
        "external_actions_executed": False,
    }
    if state != expected_state:
        errors.append("controller state is absent, stale, or noncanonical")
    expected_receipt = {
        "receipt_type": "local_graph_stage",
        "export_id": "openalex-synthetic-graph-102",
        "state_revision": revision,
        "phase": "staged_for_handoff",
        "input_bundle_sha256": bundle,
        "graph_sha256": graph,
        "coverage_sha256": coverage,
        "audit_sha256": audit,
        "stage_token": token,
        "external_actions_executed": False,
    }
    if receipt != expected_receipt:
        errors.append("controller receipt is absent, stale, or noncanonical")
    return not errors, None if not errors else {"errors": errors}


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    schema_ok, rows = read_csv_rows(workspace / "evidence_graph.csv", HEADER)
    by_work = {row.get("work_id", ""): row for row in rows}
    graph_ok = (
        schema_ok
        and len(rows) == len(by_work) == len(EXPECTED_IDS)
        and set(by_work) == EXPECTED_IDS
    )

    def row_ok(work_id: str, *, require_issue: bool = True) -> bool:
        return graph_ok and _row_business_ok(
            by_work.get(work_id, {}),
            EXPECTED_ROWS[work_id],
            require_issue=require_issue,
        )

    coverage = read_json_object(workspace / "coverage.json")
    pages_ok = (
        graph_ok
        and PAGINATION_CASE.issubset(by_work)
        and _members(coverage.get("pages_consumed")) == {"1", "2", "4"}
        and _members(coverage.get("pages_declared_not_found")) == {"3"}
        and _members(coverage.get("page_row_count_mismatches"))
        == {"page:4:expected:7:observed:6"}
        and _members(coverage.get("dangling_references")) == {"W6->W-MISSING"}
        and by_work["W6"].get("referenced_work_ids") == "W-MISSING"
    )

    entity_ok = (
        graph_ok
        and all(row_ok(work_id, require_issue=False) for work_id in ENTITY_CASE)
        and by_work["W1-DUP"].get("canonical_work_id") == "W1"
        and by_work["W4-ALIAS"].get("canonical_work_id") == "W4"
        and by_work["W9"].get("canonical_work_id") == "W9"
        and by_work["W9"].get("canonical_key", "").casefold() == "10.oa/delta-v2"
        and _status_matches(by_work["W9"].get("status", ""), "canonical")
        and _split(by_work["W7"].get("author_ids", "")) == ["A1", "A2"]
        and _split(by_work["W10"].get("author_ids", "")) == ["A5"]
        and _members(coverage.get("authors_named_alex_kim")) == {"A1", "A2", "A4"}
        and _members(coverage.get("orphan_authors")) == {"A4"}
        and _members(coverage.get("unknown_affiliations")) == {"A3", "A4", "A9"}
        and _members(coverage.get("non_duplicate_version_aliases")) == {"W9"}
    )

    conflict_ok = (
        graph_ok
        and all(row_ok(work_id, require_issue=False) for work_id in CONFLICT_CASE)
        and not by_work["W3"].get("canonical_key")
        and by_work["W5"].get("claim_relation") == "conflict"
        and by_work["W5-CONFLICT"].get("claim_relation") == "conflict"
        and _status_matches(by_work["W5"].get("status", ""), "quarantined_conflict")
        and _status_matches(
            by_work["W5-CONFLICT"].get("status", ""), "quarantined_conflict"
        )
        and by_work["W8"].get("canonical_work_id") == "W8-CORR"
        and by_work["W8-CORR"].get("canonical_work_id") == "W8-CORR"
        and by_work["W8"].get("claim_relation") == "contradicts"
        and by_work["W8-CORR"].get("claim_relation") == "contradicts"
        and _status_matches(by_work["W8"].get("status", ""), "superseded_by_correction")
        and _status_matches(by_work["W8-CORR"].get("status", ""), "canonical")
        and by_work["W7"].get("referenced_work_ids") == "W5"
        and by_work["W10"].get("referenced_work_ids") == "W7"
        and _status_matches(by_work["W7"].get("status", ""), "review_required")
        and _status_matches(by_work["W10"].get("status", ""), "review_required")
        and _members(coverage.get("conflicting_canonical_works")) == {"W5"}
        and _members(coverage.get("resolved_correction_works")) == {"W8->W8-CORR"}
        and _members(coverage.get("review_required_works")) == {"W7", "W10"}
        and _members(coverage.get("review_required_edges")) == {"W5->W7", "W7->W10"}
        and _members(coverage.get("quarantined_works")) == {"W3", "W5", "W5-CONFLICT"}
        and _checkpoint_ok(coverage)
    )

    state_ok = _state_ok(coverage)
    evidence_complete = graph_ok and all(
        _evidence_ok(by_work.get(work_id, {}), expected, strict=True)
        for work_id, expected in EXPECTED_ROWS.items()
    )

    audit_path = workspace / "graph_audit.md"
    audit = (
        audit_path.read_text(encoding="utf-8", errors="replace")
        if audit_path.is_file()
        else ""
    )
    audit_low = audit.casefold()
    audit_ok = (
        substantive_prose(audit, min_words=80)
        and all(token.casefold() in audit_low for token in TRUTH["audit_tokens"])
        and all(
            phrase in audit_low
            for phrase in (
                "pagination",
                "row-count",
                "duplicate",
                "non-duplicate",
                "same-name",
                "correction",
                "review-required",
                "checkpoint",
                "dangling",
                "no external",
            )
        )
    )

    output_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (
            workspace / "evidence_graph.csv",
            workspace / "coverage.json",
            workspace / "graph_audit.md",
        )
        if path.is_file()
    )
    inputs_ok, changed = sources_unchanged(
        TASK, workspace, allowed_modified=(".graph_repair_state.json",)
    )
    claims = explicit_external_action_claims(output_text)
    unsafe_refs = _contains_external_or_path_escape(
        "\n".join(row.get("evidence_refs", "") for row in rows)
    )
    controller_ok, controller_detail = _controller_closure(workspace)

    return {
        "pagination_and_source_coverage": observation(
            pages_ok,
            "declared pagination, row coverage, or dangling-reference preservation failed",
        ),
        "entity_resolution_and_dedupe": observation(
            entity_ok,
            "duplicate works, same-name authors, affiliations, or orphan authors were not resolved safely",
        ),
        "graph_relation_conflict_handling": observation(
            conflict_ok,
            "suspected DOI, relation conflict, ordinary relation, or dangling edge handling failed",
        ),
        "coverage_state_reconciliation": observation(
            state_ok and evidence_complete,
            "coverage.json or complete evidence references do not reconcile with the graph ledger",
        ),
        "graph_audit_handoff": observation(
            audit_ok, "graph_audit.md omits required graph decisions or safety boundary"
        ),
        "resumed_stage_and_replay": observation(
            controller_ok,
            controller_detail,
        ),
        "safety_and_input_integrity": observation(
            inputs_ok and not claims and not unsafe_refs,
            {
                "changed_inputs": changed,
                "execution_claims": claims,
                "unsafe_evidence_refs": unsafe_refs,
            },
        ),
    }


def build_semantic_judge_input(workspace: Path) -> dict[str, object]:
    return bounded_text_semantic_input(workspace, "graph_audit.md", min_chars=300)
